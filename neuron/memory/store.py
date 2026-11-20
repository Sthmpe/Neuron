"""NEURON's knowledge memory: what it learned while working, kept on disk and searchable by words and by meaning.

A note has a kind ("finding": a fact with its source; "fix": a change that made failing tests pass), the text, its
source, the date, the version it applied to, a verification status, and counters for how often it was used and how
often it really helped. Search combines full-text keyword ranking (SQLite FTS5) with meaning similarity from a small
embedding model (bge-small-en-v1.5, 37 MB, run by llama.cpp; see embed.py), merged by reciprocal rank. Without the
embedding model, a character n-gram fallback keeps meaning-ish search working.

Rules (VISION and the owner's plan): memory is searched before reasoning; a remembered fix is only a suggestion until
the tests pass again; benchmark and evaluation runs never write to memory (NEURON_MEMORY=off).
"""
import json
import math
import os
import re
import sqlite3
import time
import threading
from pathlib import Path

from ..agent.document_facts import valid_note
from .document_notes import metadata, page_finding, review_documents
from .embed import best_embedder

KINDS = ("finding", "fix", "fact")
STATUS = ("verified", "unverified", "outdated", "failed_reuse")


def memory_enabled():
    return os.environ.get("NEURON_MEMORY", "on").lower() not in ("off", "0", "no")


def _fts_query(text):
    words = [w for w in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(w) > 2][:24]
    return " OR ".join(f'"{w}"' for w in words)


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


class Memory:
    def __init__(self, path, embedder=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, kind TEXT, text TEXT, source TEXT, created REAL,
                version TEXT, status TEXT, tags TEXT, meta TEXT, vector TEXT, embedder TEXT, uses INTEGER DEFAULT 0,
                helped INTEGER DEFAULT 0, last_checked REAL);
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(text, tags, content='notes', content_rowid='id');
        """)
        self._write_lock = threading.RLock()
        self._hidden_docs = review_documents(self.db, self.path, write=memory_enabled())
        self.embedder = embedder if embedder is not None else best_embedder()

    # ---- writing ---------------------------------------------------------------------------------------------
    def add(self, kind, text, source, version="", verified=False, tags=(), meta=None):
        """Store a note; returns its id, or None when memory writes are switched off (benchmarks, evaluations)."""
        if not memory_enabled():
            return None
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        doc = page_finding(kind, source) or (kind == "finding" and "document_fact" in (meta or {}))
        if doc and verified:
            proof = (meta or {}).get("document_fact")
            if proof is not None or '(quote: "' in text:
                if not valid_note(proof, text, source):
                    return None
            else:
                verified = False  # a page reference without a checked claim is still a searchable, unverified note
        where, args = ("kind=? AND text=? AND source=?", (kind,text,source)) if doc else ("kind=? AND text=?", (kind,text))
        with self._write_lock, self.db:
            if not self.db.in_transaction:
                self.db.execute("BEGIN IMMEDIATE")
            dup = self.db.execute("SELECT id,status FROM notes WHERE "+where, args).fetchone()
            if dup:
                if doc and verified and dup["status"] != "verified":
                    self.db.execute("UPDATE notes SET status='verified',meta=?,last_checked=? WHERE id=?",
                                    (json.dumps(meta),time.time(),dup["id"]))
                    self._hidden_docs.discard(dup["id"])
                return dup["id"]
            vec = self.embedder.embed([text])[0]
            cur = self.db.execute(
                "INSERT INTO notes(kind, text, source, created, version, status, tags, meta, vector, embedder, last_checked) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (kind, text, source, time.time(), version, "verified" if verified else "unverified", " ".join(tags),
                 json.dumps(meta or {}), json.dumps([round(x, 5) for x in vec]), self.embedder.name, time.time()))
            self.db.execute("INSERT INTO notes_fts(rowid, text, tags) VALUES(?,?,?)", (cur.lastrowid, text, " ".join(tags)))
            return cur.lastrowid

    def mark(self, note_id, status=None, used=False, helped=None):
        if not memory_enabled():
            return
        with self._write_lock, self.db:
            if status == "verified":
                if not self.db.in_transaction:
                    self.db.execute("BEGIN IMMEDIATE")
                row = self.db.execute("SELECT kind,text,source,meta FROM notes WHERE id=?", (note_id,)).fetchone()
                if row:
                    proof = metadata(row["meta"]).get("document_fact")
                    if (proof or page_finding(row["kind"], row["source"])) and not valid_note(proof, row["text"], row["source"]):
                        status = None
            if status:
                self.db.execute("UPDATE notes SET status=?, last_checked=? WHERE id=?", (status, time.time(), note_id))
            if used:
                self.db.execute("UPDATE notes SET uses = uses + 1 WHERE id=?", (note_id,))
            if helped:
                self.db.execute("UPDATE notes SET helped = helped + 1 WHERE id=?", (note_id,))

    # ---- reading ---------------------------------------------------------------------------------------------
    def search(self, query, k=5, kinds=None, include_outdated=False):
        """Hybrid search. Returns notes (dicts) with 'score', best first."""
        where = "" if include_outdated else " AND n.status NOT IN ('outdated')"
        kind_sql = f" AND n.kind IN ({','.join('?' * len(kinds))})" if kinds else ""
        args = list(kinds or [])
        ranked_kw = []
        q = _fts_query(query)
        if q:
            ranked_kw = [r["id"] for r in self.db.execute(
                f"SELECT n.id FROM notes_fts f JOIN notes n ON n.id = f.rowid WHERE notes_fts MATCH ?{where}{kind_sql} "
                f"ORDER BY bm25(notes_fts) LIMIT 30", [q] + args)]
        rows = {r["id"]: dict(r) for r in self.db.execute(f"SELECT * FROM notes n WHERE 1=1{where}{kind_sql}", args)}
        if not include_outdated and self._hidden_docs:
            ranked_kw = [nid for nid in ranked_kw if nid not in self._hidden_docs]
            for nid in self._hidden_docs:
                rows.pop(nid, None)
        qv = self.embedder.embed([query])[0]
        sims = []
        for nid, r in rows.items():
            if r["embedder"] == self.embedder.name:          # vectors from another embedder are not comparable
                sims.append((nid, _cos(qv, json.loads(r["vector"]))))
        sims.sort(key=lambda x: -x[1])
        ranked_vec = [nid for nid, s in sims[:30] if s >= self.embedder.min_similarity]
        score, simd = {}, dict(sims)
        w_vec = 2.0 if self.embedder.name != "hash-3gram-512" else 1.0     # meaning counts more than a shared word
        for ranking, w in ((ranked_kw, 1.0), (ranked_vec, w_vec)):
            for rank, nid in enumerate(ranking):
                score[nid] = score.get(nid, 0) + w / (60 + rank)
        best = sorted(score, key=lambda n: (-score[n], -simd.get(n, 0.0)))[:k]
        out = []
        for nid in best:
            r = rows[nid]
            if nid in self._hidden_docs:
                r["status"] = "outdated"
            r["score"] = round(score[nid], 4)
            r["similarity"] = round(simd.get(nid, 0.0), 3)
            r["meta"] = json.loads(r["meta"] or "{}")
            r.pop("vector", None)
            out.append(r)
        return out

    def due_for_recheck(self, days=30):
        """Notes from outside sources (web pages, package docs) not checked for `days`: to check again when online."""
        cutoff = time.time() - days * 86400
        return [dict(r) for r in self.db.execute(
            "SELECT id, kind, text, source, version, status, tags FROM notes WHERE last_checked < ? AND (source LIKE 'http%' OR version != '')"
            " AND status != 'outdated'", (cutoff,))]

    def stats(self):
        r = self.db.execute("SELECT COUNT(*) n, SUM(uses) uses, SUM(helped) helped FROM notes").fetchone()
        return {"notes": r["n"], "uses": r["uses"] or 0, "helped": r["helped"] or 0, "embedder": self.embedder.name}


def context_text(notes, limit=1200):
    """Notes as a short block for a model prompt, each with its status and source, to be checked before use."""
    if not notes:
        return ""
    lines = ["Notes from NEURON's earlier work (check that each applies before relying on it):"]
    for n in notes:
        day = time.strftime("%Y-%m-%d", time.localtime(n["created"]))
        lines.append(f"- [{n['kind']}, {n['status']}, {day}, source: {n['source'][:80]}] {n['text'][:400]}")
    text = "\n".join(lines)
    return text[:limit]


def default_memory():
    home = Path(os.environ.get("NEURON_HOME", str(Path.home() / ".neuron")))
    return Memory(home / "memory" / "knowledge.db")
