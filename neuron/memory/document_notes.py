"""Recover the original evidence for document findings saved before relation checks existed."""
import json
import re
import time

from ..agent.document_facts import document_proof, legacy_identity, valid_note


def page_finding(kind, source):
    return kind == "finding" and isinstance(source, str) and re.fullmatch(r".+ page \d+", source) is not None


def metadata(value):
    try:
        data = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_rows(path):
    try:
        rows = json.loads(path.read_text())
        return [r for r in rows if isinstance(r,dict)] if isinstance(rows,list) else []
    except (OSError, ValueError):
        return []


def recover(jobs, wanted):
    """Match the original serialized note and source to a saved answer and its full indexed page."""
    found = {}
    for path in jobs.glob("*/workspace/answers.json"):
        candidates = []
        for row in read_rows(path):
            if not all(isinstance(row.get(k), str) for k in ("question","answer","doc","quote")) or type(row.get("page")) is not int:
                continue
            key = legacy_identity(row)
            if key in wanted:
                candidates.append((key,row))
        if not candidates:
            continue
        pages = read_rows(path.parent / ".neuron/job/index.json")
        for key,row in candidates:
            matches = [p.get("text") for p in pages if (p.get("doc"),p.get("page")) == (row["doc"],row["page"])]
            proof = document_proof(row,matches[0]) if len(matches)==1 else None
            # Same display source can name more than one job's file. Every matching record must support the claim.
            if key not in found or not proof:
                found[key] = proof
    return found


def review_documents(db, path, write):
    """Retire unsupported verified findings before retrieval. Keep IDs, text, FTS rows and usage history."""
    hidden = set()
    with db:
        if write:
            db.execute("BEGIN IMMEDIATE")
        legacy = []
        for row in db.execute("SELECT id,text,source,meta FROM notes WHERE kind='finding' AND status='verified' AND source LIKE '% page %'"):
            if not page_finding("finding",row["source"]):
                continue
            meta = metadata(row["meta"])
            if not valid_note(meta.get("document_fact"),row["text"],row["source"]):
                legacy.append((row,meta))
        if not legacy:
            return hidden
        home = path.parent.parent if path.parent.name=="memory" else path.parent
        known = recover(home/"jobs", {(r["text"],r["source"]) for r,_ in legacy})
        for row,meta in legacy:
            proof = known.get((row["text"],row["source"]))
            if proof:
                meta["document_fact"] = proof
            else:
                hidden.add(row["id"])
                meta["document_review"] = "Original page unavailable or the cited evidence does not establish this fact."
            if write:
                db.execute("UPDATE notes SET status=?,meta=?,last_checked=? WHERE id=?",
                           ("verified" if proof else "outdated",json.dumps(meta),time.time(),row["id"]))
    return set() if write else hidden
