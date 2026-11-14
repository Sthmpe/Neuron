"""Task store: every task, step, status and result lives in SQLite.

Each public method is one transaction, so a change is on disk the moment the
method returns. If the brain process is killed, the database still holds the
exact state the engine had reached.
"""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
    id TEXT PRIMARY KEY, goal TEXT, status TEXT, planner TEXT,
    created_at REAL, start_at REAL, updated_at REAL, finished_at REAL,
    retry_count INTEGER DEFAULT 0, next_retry_at REAL);
CREATE TABLE IF NOT EXISTS steps(
    task_id TEXT, no INTEGER, title TEXT, action TEXT, params TEXT,
    needs_internet INTEGER, sensitive INTEGER, depends_on TEXT,
    status TEXT, attempts INTEGER DEFAULT 0,
    result TEXT, proof TEXT, error TEXT, started_at REAL, finished_at REAL,
    PRIMARY KEY(task_id, no));
CREATE TABLE IF NOT EXISTS executions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, step_no INTEGER,
    attempt INTEGER, started_at REAL, finished_at REAL, outcome TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS permissions(
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, step_no INTEGER,
    description TEXT, status TEXT, requested_at REAL, decided_at REAL,
    UNIQUE(task_id, step_no));
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, at REAL,
    kind TEXT, message TEXT);
"""

JSON_COLS = {"params", "depends_on", "result", "proof"}


def _row(cur, row):
    d = {}
    for i, col in enumerate(cur.description):
        name, val = col[0], row[i]
        if name in JSON_COLS and val is not None:
            val = json.loads(val)
        elif name in ("needs_internet", "sensitive"):
            val = bool(val)
        d[name] = val
    return d


class Store:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = _row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        """Add step-2 columns to a database created by v0.1."""
        wanted = {"steps": [("reviewed", "INTEGER DEFAULT 0"), ("superseded", "INTEGER DEFAULT 0")],
                  "tasks": [("revisions", "INTEGER DEFAULT 0"), ("note", "TEXT")]}
        for table, cols in wanted.items():
            have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})").fetchall()}
            for name, decl in cols:
                if name not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    @contextmanager
    def _tx(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    def _q(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def _ev(self, task_id, kind, message):
        self.db.execute("INSERT INTO events(task_id, at, kind, message) VALUES(?,?,?,?)",
                        (task_id, self.clock(), kind, message))

    def _update(self, table, where, where_args, fields):
        if not fields:
            return
        cols, vals = [], []
        for k, v in fields.items():
            cols.append(f"{k}=?")
            vals.append(json.dumps(v) if k in JSON_COLS and v is not None else v)
        self.db.execute(f"UPDATE {table} SET {', '.join(cols)} WHERE {where}", vals + list(where_args))

    # ---- tasks -----------------------------------------------------------
    def create_task(self, goal, plan, planner_name, start_at=None):
        now = self.clock()
        task_id = uuid.uuid4().hex[:8]
        scheduled = start_at is not None and start_at > now
        with self._tx():
            self.db.execute(
                "INSERT INTO tasks(id, goal, status, planner, created_at, start_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (task_id, goal, "scheduled" if scheduled else "running", planner_name, now, start_at, now))
            for s in plan:
                self.db.execute(
                    "INSERT INTO steps(task_id, no, title, action, params, needs_internet, sensitive, "
                    "depends_on, status) VALUES(?,?,?,?,?,?,?,?,?)",
                    (task_id, s.no, s.title, s.action, json.dumps(s.params), int(s.needs_internet),
                     int(s.sensitive), json.dumps(s.depends_on), "pending"))
            self._ev(task_id, "task", f"task received and planned into {len(plan)} steps"
                     + (" (scheduled for later)" if scheduled else ""))
        return task_id

    def get_task(self, task_id):
        rows = self._q("SELECT * FROM tasks WHERE id=?", (task_id,))
        return rows[0] if rows else None

    def list_tasks(self):
        return self._q("SELECT * FROM tasks ORDER BY created_at")

    def active_tasks(self):
        return self._q("SELECT * FROM tasks WHERE status NOT IN ('done','failed') ORDER BY created_at")

    def set_task(self, task_id, event=None, **fields):
        fields["updated_at"] = self.clock()
        with self._tx():
            self._update("tasks", "id=?", (task_id,), fields)
            if event:
                self._ev(task_id, *event)

    # ---- steps -----------------------------------------------------------
    def steps(self, task_id):
        return self._q("SELECT * FROM steps WHERE task_id=? ORDER BY no", (task_id,))

    def set_step(self, task_id, no, event=None, **fields):
        with self._tx():
            self._update("steps", "task_id=? AND no=?", (task_id, no), fields)
            if event:
                self._ev(task_id, *event)

    def mark_pending_as(self, task_id, status):
        with self._tx():
            self.db.execute("UPDATE steps SET status=? WHERE task_id=? AND status='pending'", (status, task_id))

    def begin_execution(self, task_id, no):
        """Mark a step as running BEFORE it runs, so a crash mid-step is visible."""
        now = self.clock()
        with self._tx():
            self.db.execute("UPDATE steps SET status='running', attempts=attempts+1, started_at=? "
                            "WHERE task_id=? AND no=?", (now, task_id, no))
            attempt = self.db.execute("SELECT attempts FROM steps WHERE task_id=? AND no=?",
                                      (task_id, no)).fetchone()["attempts"]
            cur = self.db.execute("INSERT INTO executions(task_id, step_no, attempt, started_at) "
                                  "VALUES(?,?,?,?)", (task_id, no, attempt, now))
            self._ev(task_id, "step", f"step {no} started (attempt {attempt})")
            return attempt, cur.lastrowid

    def end_execution(self, exec_id, task_id, no, outcome, event, detail=None, **step_fields):
        """The checkpoint: step status + result + proof saved in ONE transaction."""
        now = self.clock()
        with self._tx():
            self.db.execute("UPDATE executions SET finished_at=?, outcome=?, detail=? WHERE id=?",
                            (now, outcome, detail, exec_id))
            if outcome in ("done", "failed"):
                step_fields["finished_at"] = now
            self._update("steps", "task_id=? AND no=?", (task_id, no), step_fields)
            self._ev(task_id, *event)

    def recover_interrupted(self):
        """After a restart: anything left 'running' was cut off mid-step."""
        with self._tx():
            rows = self.db.execute("SELECT task_id, no FROM steps WHERE status='running'").fetchall()
            for r in rows:
                self.db.execute("UPDATE steps SET status='pending' WHERE task_id=? AND no=?",
                                (r["task_id"], r["no"]))
                self._ev(r["task_id"], "recovery",
                         f"step {r['no']} was interrupted by a restart; it will run again with the same "
                         "idempotency key so its outside effect cannot happen twice")
            self.db.execute("UPDATE executions SET outcome='interrupted', finished_at=? "
                            "WHERE outcome IS NULL", (self.clock(),))
            return [(r["task_id"], r["no"]) for r in rows]

    def apply_review(self, task_id, no, decision, reason, new_steps=()):
        """Record the planner's look at a finished step, in ONE transaction.

        continue - nothing changes.
        revise   - steps that have not run yet are dropped and `new_steps` are appended.
                   If the reviewed step had failed it is marked superseded (another approach replaces it).
        give_up  - steps that have not run yet are dropped; the task will end as failed.
        """
        with self._tx():
            self.db.execute("UPDATE steps SET reviewed=1 WHERE task_id=? AND no=?", (task_id, no))
            if decision == "continue":
                self._ev(task_id, "review", f"reviewed step {no}: carry on - {reason}")
                return
            self.db.execute("DELETE FROM permissions WHERE task_id=? AND step_no IN (SELECT no FROM steps "
                            "WHERE task_id=? AND status NOT IN ('done','failed','rejected','blocked','running'))",
                            (task_id, task_id))
            self.db.execute("DELETE FROM steps WHERE task_id=? AND status NOT IN "
                            "('done','failed','rejected','blocked','running')", (task_id,))
            if decision == "revise":
                self.db.execute("UPDATE steps SET superseded=1 WHERE task_id=? AND no=? AND status='failed'",
                                (task_id, no))
                last = self.db.execute("SELECT MAX(no) AS m FROM steps WHERE task_id=?", (task_id,)).fetchone()["m"]
                prev = None
                for i, s in enumerate(new_steps, 1):
                    self.db.execute(
                        "INSERT INTO steps(task_id, no, title, action, params, needs_internet, sensitive, "
                        "depends_on, status) VALUES(?,?,?,?,?,?,?,?,?)",
                        (task_id, last + i, s.title, s.action, json.dumps(s.params), int(s.needs_internet),
                         int(s.sensitive), json.dumps([prev] if prev else []), "pending"))
                    prev = last + i
                self.db.execute("UPDATE tasks SET revisions=revisions+1 WHERE id=?", (task_id,))
                self._ev(task_id, "revision", f"plan revised after step {no}: {reason} "
                         f"(new steps: {', '.join(s.action for s in new_steps)})")
            else:
                self.db.execute("UPDATE tasks SET note=? WHERE id=?", (reason, task_id))
                self._ev(task_id, "revision", f"planner gave up after step {no}: {reason}")

    def executions(self, task_id):
        return self._q("SELECT * FROM executions WHERE task_id=? ORDER BY id", (task_id,))

    # ---- permissions -----------------------------------------------------
    def request_permission(self, task_id, no, description):
        with self._tx():
            self.db.execute("INSERT INTO permissions(task_id, step_no, description, status, requested_at) "
                            "VALUES(?,?,?,?,?)", (task_id, no, description, "pending", self.clock()))
            self.db.execute("UPDATE steps SET status='waiting_approval' WHERE task_id=? AND no=?",
                            (task_id, no))
            self._ev(task_id, "permission", f"step {no} is sensitive - asking the host for approval")

    def get_permission(self, task_id, no):
        rows = self._q("SELECT * FROM permissions WHERE task_id=? AND step_no=?", (task_id, no))
        return rows[0] if rows else None

    def list_permissions(self, status=None):
        if status:
            return self._q("SELECT * FROM permissions WHERE status=? ORDER BY id", (status,))
        return self._q("SELECT * FROM permissions ORDER BY id")

    def decide_permission(self, perm_id, decision):
        assert decision in ("approved", "rejected")
        with self._tx():
            row = self.db.execute("SELECT * FROM permissions WHERE id=?", (perm_id,)).fetchone()
            if not row:
                return None
            if row["status"] == "pending":
                self.db.execute("UPDATE permissions SET status=?, decided_at=? WHERE id=?",
                                (decision, self.clock(), perm_id))
                self._ev(row["task_id"], "permission", f"host {decision} step {row['step_no']}")
            return self.db.execute("SELECT * FROM permissions WHERE id=?", (perm_id,)).fetchone()

    # ---- events ----------------------------------------------------------
    def add_event(self, task_id, kind, message):
        with self._tx():
            self._ev(task_id, kind, message)

    def events(self, task_id=None, after=0):
        if task_id:
            return self._q("SELECT * FROM events WHERE id>? AND (task_id=? OR task_id IS NULL) ORDER BY id",
                           (after, task_id))
        return self._q("SELECT * FROM events WHERE id>? ORDER BY id", (after,))
