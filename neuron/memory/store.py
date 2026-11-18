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
from pathlib import Path

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
        self.embedder = embedder if embedder is not None else best_embedder()

    # ---- writing ---------------------------------------------------------------------------------------------
    def add(self, kind, text, source, version="", verified=False, tags=(), meta=None):
        """Store a note; returns its id, or None when memory writes are switched off (benchmarks, evaluations)."""
        if not memory_enabled():
            return None
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        dup = self.db.execute("SELECT id FROM notes WHERE kind=? AND text=?", (kind, text)).fetchone()
        if dup:
            return dup["id"]
        vec = self.embedder.embed([text])[0]
        cur = self.db.execute(
            "INSERT INTO notes(kind, text, source, created, version, status, tags, meta, vector, embedder, last_checked) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (kind, text, source, time.time(), version, "verified" if verified else "unverified", " ".join(tags),
             json.dumps(meta or {}), json.dumps([round(x, 5) for x in vec]), self.embedder.name, time.time()))
        self.db.execute("INSERT INTO notes_fts(rowid, text, tags) VALUES(?,?,?)", (cur.lastrowid, text, " ".join(tags)))
        self.db.commit()
        return cur.lastrowid

    def mark(self, note_id, status=None, used=False, helped=None):
        if status:
            self.db.execute("UPDATE notes SET status=?, last_checked=? WHERE id=?", (status, time.time(), note_id))
        if used:
            self.db.execute("UPDATE notes SET uses = uses + 1 WHERE id=?", (note_id,))
        if helped:
            self.db.execute("UPDATE notes SET helped = helped + 1 WHERE id=?", (note_id,))
        self.db.commit()

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
