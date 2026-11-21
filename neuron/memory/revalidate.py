"""Re-check saved document findings whenever the rules that confirmed them become stricter.

A finding saved as verified by an older, looser check can be wrong (Astra's review of main d54bf4d: "16 yellow chairs"
was saved as verified although the page said 3). On start, every verified document finding is checked again with the
current rule; any that fails is marked "rejected": kept for history, never returned by search, never offered as
evidence. Runs once per rule version (recorded in the database), so it costs nothing on later starts.
"""
import json
import re

RULE_VERSION = "doc-facts-3"           # bump when facts_backed becomes stricter (3: Astra's relation matcher)
OLD_TEXT = re.compile(r"(.+?\?)\s+(.*?)\s+\(quote: \"(.*)\"\)$", re.S)


def revalidate_findings(memory, log=print):
    from ..agent.capabilities.research import facts_backed
    db = memory.db
    db.execute("CREATE TABLE IF NOT EXISTS checks(rule TEXT PRIMARY KEY, at REAL)")
    if db.execute("SELECT 1 FROM checks WHERE rule=?", (RULE_VERSION,)).fetchone():
        return {"checked": 0, "rejected": 0, "skipped": "already checked under " + RULE_VERSION}
    checked = rejected = 0
    for row in db.execute("SELECT id, text, meta FROM notes WHERE kind='finding' AND status='verified'").fetchall():
        meta = json.loads(row["meta"] or "{}")
        q, a, quote = meta.get("question"), meta.get("answer"), meta.get("quote")
        if not (q and quote):
            m = OLD_TEXT.match(row["text"] or "")
            if not m:
                continue
            q, a, quote = m.groups()
        checked += 1
        if not facts_backed(q, a or "", quote, meta.get("page_text") or None):
            memory.mark(row["id"], status="rejected")
            meta["rejected_by"] = RULE_VERSION
            db.execute("UPDATE notes SET meta=? WHERE id=?", (json.dumps(meta), row["id"]))
            rejected += 1
            log(f"memory: finding {row['id']} rejected by the stricter document check: {(row['text'] or '')[:100]}")
    import time
    db.execute("INSERT OR REPLACE INTO checks VALUES(?, ?)", (RULE_VERSION, time.time()))
    db.commit()
    return {"checked": checked, "rejected": rejected}
