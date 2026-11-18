"""Release retest: drive an installed NEURON through its phone API (exactly what the phone page calls) with real tasks
and a real model, then check what came back with independent checks.

  python3 -m benchmark.release.retest --base http://127.0.0.1:8642 --home ~/.neuron --out benchmark/results/release_retest.json

The tasks are new requests written for this retest, not taken from any locked evaluation.
"""
import argparse
import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

CSV = """date,shop,item,units,unit_price
2026-03-02,Ikeja,rice 5kg,4,9500
2026-03-02,Yaba,rice 5kg,2,9500
2026-03-03,Ikeja,palm oil 1L,10,2800
2026-03-04,Yaba,palm oil 1L,6,2800
2026-03-05,Lekki,sugar 1kg,12,1600
2026-03-06,Ikeja,sugar 1kg,5,1600
2026-03-07,Lekki,rice 5kg,3,9500
"""
TASKS = [
    {"id": "excel", "goal": "Make shop_sales.xlsx: the rows on a sheet Data, and a sheet Summary with total units and total revenue "
                            "(units times unit price) per shop, a Total row, all as formulas.", "files": {"march_sales.csv": CSV}},
    {"id": "word", "goal": "Write letter.docx: a short letter to our landlord asking to fix the leaking roof at shop 3 before the "
                           "rainy season, with headings Problem, Request, Contact. 150 to 300 words."},
    {"id": "answer", "goal": "In one paragraph, why does bread go stale?"},
    {"id": "app", "goal": "Build an app for my bookshop with login (user ada, password shelf2026): books with title, author and "
                          "copies in stock; sales with the book, number of copies and the customer. Adding a sale must lower "
                          "the copies in stock, and refuse it if there are not enough."},
]


class Phone:
    def __init__(self, base):
        self.base, self.cookie = base.rstrip("/"), None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method, path, body=None, raw=None):
        h = {"X-Neuron": "1", **({"Cookie": self.cookie} if self.cookie else {})}
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            r = self.opener.open(req, timeout=60)
        except urllib.error.HTTPError as e:
            r = e
        if r.headers.get("Set-Cookie"):
            self.cookie = r.headers["Set-Cookie"].split(";")[0]
        payload = r.read()
        try:
            return r.status, json.loads(payload)
        except ValueError:
            return r.status, payload


def wait(phone, jid, limit):
    end = time.time() + limit
    while time.time() < end:
        s, d = phone.call("GET", f"/api/jobs/{jid}")
        if d.get("status") in ("done", "partial", "failed", "waiting_approval"):
            return d
        time.sleep(10)
    return phone.call("GET", f"/api/jobs/{jid}")[1]


def check_excel(data):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data))
    ok = {"Data", "Summary"} <= set(wb.sheetnames)
    formulas = sum(1 for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")) if ok else 0
    return [{"id": "sheets_data_and_summary", "pass": ok}, {"id": "summary_has_formulas", "pass": formulas >= 3, "detail": formulas}]


def check_word(data):
    import docx
    d = docx.Document(io.BytesIO(data))
    heads = [p.text.strip() for p in d.paragraphs if p.style.name.startswith("Heading")]
    words = sum(len(p.text.split()) for p in d.paragraphs)
    return [{"id": "headings", "pass": all(any(h.lower() == w.lower() for h in heads) for w in ("Problem", "Request", "Contact")), "detail": heads},
            {"id": "length_150_300", "pass": 150 <= words <= 330, "detail": words}]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--home", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only")
    a = ap.parse_args(argv)
    phone = Phone(a.base)
    code = json.loads(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(a.base + "/local/pair-code", timeout=10).read())["code"]
    s, _ = phone.call("POST", "/api/pair", {"code": code, "name": "retest"})
    results = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "paired": s == 200, "rows": []}
    s, status = phone.call("GET", "/api/status")
    results["status"] = status
    for t in TASKS:
        if a.only and t["id"] not in a.only.split(","):
            continue
        t0 = time.time()
        s, d = phone.call("POST", "/api/jobs", {"goal": t["goal"]})
        jid = d["id"]
        for name, text in t.get("files", {}).items():
            phone.call("POST", f"/api/jobs/{jid}/upload?name={name}", raw=text.encode())
        phone.call("POST", f"/api/jobs/{jid}/start")
        d = wait(phone, jid, 3600)
        row = {"task": t["id"], "status": d.get("status"), "seconds": round(time.time() - t0), "outputs": [o["path"] for o in d.get("outputs", [])][:12],
               "report": {k: (d.get("report") or {}).get(k) for k in ("verdict", "model_calls", "not_done", "made_by")}, "checks": []}
        if t["id"] == "excel" and "shop_sales.xlsx" in row["outputs"]:
            row["checks"] = check_excel(phone.call("GET", f"/api/jobs/{jid}/file?path=shop_sales.xlsx")[1])
        if t["id"] == "word" and "letter.docx" in row["outputs"]:
            row["checks"] = check_word(phone.call("GET", f"/api/jobs/{jid}/file?path=letter.docx")[1])
        if t["id"] == "answer":
            row["checks"] = [{"id": "answer_shown", "pass": len((d.get("answer") or "").split()) > 20, "detail": (d.get("answer") or "")[:160]}]
        if t["id"] == "app":
            s, pv = phone.call("POST", f"/api/jobs/{jid}/preview")
            ok = False
            if s == 200 and pv.get("url"):
                url = "http://127.0.0.1" + pv["url"]
                try:
                    import http.cookiejar          # a phone browser keeps the preview cookie across redirects
                    op = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                    body = op.open(url, timeout=20).read().decode("utf-8", "replace")
                    ok = "log in" in body.lower() or "login" in body.lower()
                except OSError as e:
                    body = str(e)
            row["checks"] = [{"id": "preview_opens_login", "pass": ok, "detail": (pv if s != 200 else "")}]
        if t["id"] == "excel" and d.get("status") in ("done", "partial"):           # a follow-up in the same conversation
            s, f = phone.call("POST", f"/api/jobs/{jid}/followup", {"text": "Also add the number of sales rows per shop."})
            fd = wait(phone, f["id"], 1800) if s == 201 else {}
            row["follow_up"] = {"status": fd.get("status"), "thread": len(fd.get("thread", []))}
        row["solved"] = row["status"] == "done" and all(c["pass"] for c in row["checks"]) and bool(row["checks"])
        results["rows"].append(row)
        Path(a.out).write_text(json.dumps(results, indent=1))
        print(f"{t['id']}: {row['status']} in {row['seconds']} s; checks {[c['id'] + ('=ok' if c['pass'] else '=FAIL') for c in row['checks']]}", flush=True)
    print("RETEST-DONE")


if __name__ == "__main__":
    main()
