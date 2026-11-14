"""The fake outside world: a pretend internet with fake company data.

Everything the brain does "online" goes through `FakeWorld.call`, which
  * refuses to work when the simulated network switch is off, and
  * writes one row per real outside action into its own ledger (world.db).

The ledger is independent of the brain's own database. That makes it the
neutral witness for "did anything happen twice?".

Each call carries an idempotency key (task id + step number). If the same key
arrives again, the world returns the stored answer instead of acting again and
counts the blocked duplicate - the same trick real payment/messaging APIs use.
"""
import hashlib
import json
import sqlite3
import threading
import time

from .network import NetworkDown

ADJ = ["Lagoon", "Savanna", "Harbour", "Baobab", "Zuma", "Niger", "Delta", "Atlas", "Kola", "Sahel"]
NOUN = ["Logistics", "Foods", "Solar"]
CITIES = ["Lagos", "Abuja", "Ibadan", "Accra", "Nairobi"]


def _h(text):
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def company(i):
    name = f"{ADJ[i % 10]} {NOUN[i // 10]}"
    return {"name": name, "industry": NOUN[i // 10], "city": CITIES[_h(name) % len(CITIES)]}


def profile(name):
    slug = name.lower().replace(" ", "")
    return {"name": name, "employees": 5 + _h(name + "emp") % 300,
            "website": f"https://{slug}.example", "email": f"info@{slug}.example"}


# page 3 deliberately repeats two companies from earlier pages
PAGES = {1: list(range(0, 10)), 2: list(range(10, 20)), 3: list(range(20, 28)) + [3, 12]}
EXISTING_CONTACTS = [company(i)["name"] for i in (1, 14, 22)]


class FakeWorld:
    def __init__(self, path, switch, clock=time.time):
        self.switch, self.clock = switch, clock
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "key TEXT UNIQUE, action TEXT, payload TEXT, result TEXT, at REAL, "
                        "duplicates_blocked INTEGER DEFAULT 0)")

    def call(self, key, action, payload):
        """Do one outside action. Returns (result, receipt)."""
        if not self.switch.is_online():
            raise NetworkDown(f"no connection while trying to {action}")
        with self.lock:
            row = self.db.execute("SELECT id, result, at FROM ledger WHERE key=?", (key,)).fetchone()
            if row:
                self.db.execute("UPDATE ledger SET duplicates_blocked=duplicates_blocked+1 WHERE key=?", (key,))
                return json.loads(row[1]), {"receipt_id": row[0], "at": row[2], "replayed": True}
            result = getattr(self, "_" + action)(**payload)
            now = self.clock()
            cur = self.db.execute("INSERT INTO ledger(key, action, payload, result, at) VALUES(?,?,?,?,?)",
                                  (key, action, json.dumps(payload), json.dumps(result), now))
            return result, {"receipt_id": cur.lastrowid, "at": now, "replayed": False}

    def ledger(self, prefix=""):
        with self.lock:
            rows = self.db.execute("SELECT id, key, action, at, duplicates_blocked FROM ledger "
                                   "WHERE key LIKE ? ORDER BY id", (prefix + "%",)).fetchall()
        return [{"receipt_id": r[0], "key": r[1], "action": r[2], "at": r[3],
                 "duplicates_blocked": r[4]} for r in rows]

    # ---- fake services ---------------------------------------------------
    def _search_directory(self, page):
        return [company(i) for i in PAGES[page]]

    def _fetch_profiles(self, names):
        return [profile(n) for n in names]

    def _verify_emails(self, emails):
        return {e: _h(e) % 5 != 0 for e in emails}

    def _send_message(self, to, body):
        return {"delivered_to": to, "chars": len(body)}

    def _crm_sync(self, rows):
        return {"synced": rows}

    def _generic(self, what):
        return {"did": what}
