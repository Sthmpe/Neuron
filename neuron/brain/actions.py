"""What each kind of step actually does. All data is fake.

Every action returns (result, summary, evidence):
  result   - data that later steps use
  summary  - one plain sentence saying what happened
  evidence - the proof: file hashes, counts, receipts from the outside world
"""
import csv
import hashlib
import io
import json

from .world import EXISTING_CONTACTS


class Ctx:
    def __init__(self, task, step, deps, world, artifacts):
        self.task, self.step, self.deps, self.world = task, step, deps, world
        self.params = step["params"] or {}
        self.key = f"{task['id']}:{step['no']}"  # idempotency key
        self.dir = artifacts / task["id"]

    def online(self, action, **payload):
        return self.world.call(self.key, action, payload)

    def write(self, name, text):
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / name
        path.write_text(text)
        return {"file": str(path), "bytes": len(text.encode()),
                "sha256": hashlib.sha256(text.encode()).hexdigest()}


def load_brief(c):
    brief = {"industries": ["Logistics", "Solar"], "min_employees": 20,
             "cities": ["Lagos", "Abuja", "Accra"]}
    return brief, "Loaded target criteria from the brief", c.write("brief.json", json.dumps(brief, indent=1))


def load_contacts(c):
    return ({"contacts": EXISTING_CONTACTS},
            f"Loaded {len(EXISTING_CONTACTS)} existing contacts", {"count": len(EXISTING_CONTACTS)})


def search_directory(c):
    companies, receipt = c.online("search_directory", page=c.params["page"])
    return ({"companies": companies}, f"Directory page {c.params['page']} returned {len(companies)} companies",
            {"receipt": receipt, "count": len(companies), "first": companies[0]["name"]})


def merge_results(c):
    merged = [co for no in (3, 4, 5) for co in c.deps[no]["companies"]]
    return {"companies": merged}, f"Merged 3 pages into {len(merged)} rows", {"rows": len(merged)}


def dedupe(c):
    known, seen, out, dupes, already = set(c.deps[2]["contacts"]), set(), [], 0, 0
    for co in c.deps[6]["companies"]:
        if co["name"] in seen:
            dupes += 1
        elif co["name"] in known:
            already += 1
        else:
            seen.add(co["name"])
            out.append(co)
    half = (len(out) + 1) // 2
    return ({"batch1": out[:half], "batch2": out[half:]},
            f"Kept {len(out)} new companies ({dupes} duplicates and {already} known contacts removed)",
            {"kept": len(out), "duplicates_removed": dupes, "known_removed": already})


def fetch_profiles(c):
    batch = c.deps[7][f"batch{c.params['batch']}"]
    profiles, receipt = c.online("fetch_profiles", names=[co["name"] for co in batch])
    full = [{**co, **p} for co, p in zip(batch, profiles)]
    return ({"profiles": full}, f"Fetched {len(full)} company profiles (batch {c.params['batch']})",
            {"receipt": receipt, "count": len(full)})


def score_leads(c):
    brief = c.deps[1]
    src = c.deps[8 if c.params["batch"] == 1 else 9]["profiles"]
    leads = [{**p, "score": 40 * (p["industry"] in brief["industries"])
              + 30 * (p["employees"] >= brief["min_employees"]) + 30 * (p["city"] in brief["cities"])}
             for p in src]
    best = max(leads, key=lambda l: l["score"])
    return ({"leads": leads}, f"Scored {len(leads)} leads in batch {c.params['batch']}",
            {"count": len(leads), "best": best["name"], "best_score": best["score"]})


def draft_template(c):
    text = "Hello {name} team,\n\nWe help {industry} companies in {city} grow. Could we talk this week?\n"
    return {"template": text}, "Drafted the outreach template", c.write("template.txt", text)


def save_interim(c):
    leads = c.deps[10]["leads"]
    ev = c.write("interim_leads.json", json.dumps(leads, indent=1))
    return {"saved": len(leads)}, f"Saved {len(leads)} interim leads to disk", ev


def verify_emails(c):
    leads = [l for no in (10, 11) for l in c.deps[no]["leads"] if l["score"] >= 60]
    valid, receipt = c.online("verify_emails", emails=[l["email"] for l in leads])
    leads = [{**l, "email_valid": valid[l["email"]]} for l in leads]
    good = sum(l["email_valid"] for l in leads)
    return ({"leads": leads}, f"Checked {len(leads)} emails, {good} are valid",
            {"receipt": receipt, "checked": len(leads), "valid": good})


def rank_leads(c):
    leads = sorted((l for l in c.deps[14]["leads"] if l["email_valid"]),
                   key=lambda l: (-l["score"], -l["employees"], l["name"]))[:10]
    return ({"leads": leads}, f"Ranked the final {len(leads)} leads",
            {"count": len(leads), "top": leads[0]["name"] if leads else None})


def personalise(c):
    tpl = c.deps[12]["template"]
    msgs = [{"to": l["email"], "name": l["name"], "body": tpl.format(**l)} for l in c.deps[15]["leads"][:3]]
    ev = c.write("messages.json", json.dumps(msgs, indent=1))
    return {"messages": msgs}, f"Wrote {len(msgs)} personalised messages", ev


def write_csv(c):
    leads = c.deps[15]["leads"]
    buf = io.StringIO()
    cols = ["name", "industry", "city", "employees", "email", "score"]
    w = csv.DictWriter(buf, cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(leads)
    ev = c.write("leads.csv", buf.getvalue())
    return {"rows": len(leads), "file": ev["file"]}, f"Wrote leads.csv with {len(leads)} rows", {**ev, "rows": len(leads)}


def send_message(c):
    msg = c.deps[16]["messages"][0]
    result, receipt = c.online("send_message", to=msg["to"], body=msg["body"])
    return ({"sent_to": msg["to"]}, f"Sent the intro message to {msg['name']} ({msg['to']})",
            {"receipt": receipt, **result})


def crm_sync(c):
    result, receipt = c.online("crm_sync", rows=c.deps[17]["rows"])
    return result, f"Synced {result['synced']} leads to the cloud CRM", {"receipt": receipt}


def write_summary(c):
    sent = c.deps.get(18)
    text = (f"Find-leads task {c.task['id']}\n"
            f"Leads synced to CRM: {c.deps[19]['synced']}\n"
            f"Intro message: {'sent to ' + sent['sent_to'] if sent else 'NOT sent (host rejected it)'}\n")
    return {"message_sent": bool(sent)}, "Wrote the final summary", c.write("summary.txt", text)


def generic(c):
    """Stand-in for steps the rule-based planner does not know how to really do."""
    if c.step["needs_internet"]:
        _, receipt = c.online("generic", what=c.step["title"])
        return {"simulated": True}, f"Simulated (online): {c.step['title']}", {"receipt": receipt}
    return {"simulated": True}, f"Simulated (offline): {c.step['title']}", {"note": "no real work done"}


ACTIONS = {f.__name__: f for f in (
    load_brief, load_contacts, search_directory, merge_results, dedupe, fetch_profiles, score_leads,
    draft_template, save_interim, verify_emails, rank_leads, personalise, write_csv, send_message,
    crm_sync, write_summary, generic)}
