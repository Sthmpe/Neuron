"""Word documents. What the request states exactly (headings, order, word range, table rows) is parsed by
code and never left to the model; the model writes the prose, section by section."""
import re
from pathlib import Path

from ...kit_next.copy import clean
from ..capability import Capability, Outcome, Verdict

EM = re.compile(r"[—―]")


def parse_request(req):
    out = {}
    m = re.search(r"\b([\w-]+\.docx)\b", req)
    out["file"] = m.group(1) if m else "document.docx"
    m = re.search(r"headings?(?: in this order)?\s*:?\s*([^.]+?)(?:\.|$)", req, re.I)
    if m:
        heads = [h.strip(" '\"") for h in re.split(r",\s*|\s+and\s+", re.sub(r"(?i)\bin this order\b|^.*?:\s*", "", m.group(1))) if h.strip()]
        out["headings"] = [h for h in heads if 0 < len(h) < 40]
    m = re.search(r"between (\d+) and (\d+) words|(\d+) to (\d+) words", req, re.I)
    if m:
        a, b = [int(x) for x in m.groups() if x]
        out["words"] = [a, b]
    m = re.search(r"table with the columns (.+?) and (.+?) and these rows:\s*(.+?)(?:, then a total row|\.\s|$)", req, re.I)
    if m:
        rows = []
        for item in re.split(r",\s*", m.group(3)):
            mm = re.match(r"(.+?)\s+([\d,.]+)$", item.strip())
            if mm:
                rows.append([mm.group(1).strip(), float(mm.group(2).replace(",", ""))])
        sec = re.search(r"The (\w+) section must have a table", req, re.I)
        out["table"] = {"columns": [m.group(1).strip(), m.group(2).strip()], "rows": rows,
                        "total": bool(re.search(r"total row", req, re.I)), "section": sec.group(1) if sec else None}
    return out


class PlanDocument(Capability):
    name = "plan_document"
    purpose = "Outline a document: title, headings in order, what each section says, tables, length"
    permissions = ("use_model",)
    resources = {"ram_mb": 50, "uses_model": True}
    verification = "headings and tables the owner listed are kept exactly"
    domains = ("documents",)

    def run(self, job, params):
        req = job.state.goal()["request"]
        fixed = parse_request(req)
        schema = {"type": "object", "required": ["title", "sections"],
                  "properties": {"title": {"type": "string"},
                                 "sections": {"type": "array", "minItems": 1, "maxItems": 10, "items": {
                                     "type": "object", "required": ["heading", "points"],
                                     "properties": {"heading": {"type": "string"}, "points": {"type": "string"}}}}}}
        hint = f"Use exactly these headings, in this order: {', '.join(fixed['headings'])}." if fixed.get("headings") else "Choose 3 to 6 short headings."
        data = job.ask_json("planner", "You outline documents.", f"Request: {req}\n\n{hint} For each section, say in one sentence what it covers.",
                            schema, max_tokens=600)
        if not data:
            return Outcome(False, "the model gave no outline")
        sections = data["sections"]
        if fixed.get("headings"):                       # the owner's headings win, in the owner's order
            by = {s["heading"].strip().lower(): s for s in sections}
            sections = [{"heading": h, "points": (by.get(h.lower()) or {}).get("points", "")} for h in fixed["headings"]]
        plan = {**fixed, "title": clean(data["title"]), "sections": sections}
        return Outcome(True, f"{len(sections)} sections: {', '.join(s['heading'] for s in sections)}", plan, made_by="model")

    def verify(self, job, params, outcome):
        p = outcome.result
        ok = bool(p["sections"]) and (not p.get("headings") or [s["heading"] for s in p["sections"]] == p["headings"])
        return Verdict(ok, [{"id": "outline_keeps_owner_headings", "pass": ok, "detail": [s["heading"] for s in p["sections"]]}], "outline check")


class WriteDocument(Capability):
    name = "write_document"
    purpose = "Write each section with the local model and assemble a styled Word document"
    permissions = ("write_workspace", "use_model")
    resources = {"ram_mb": 80, "uses_model": True}
    requires = {"binaries": [], "modules": ["docx"]}
    verification = "structure, length and tables are checked by check_document"
    domains = ("documents",)
    strategies = ("rewrite sections to fit the length", "rewrite every section")

    def run(self, job, params):
        from docx import Document
        from docx.shared import Pt, RGBColor
        p = job.state.task("outline")["result"]
        req = job.state.goal()["request"]
        lo, hi = p.get("words", [300, 800])
        per = max(40, int((lo + hi) / 2 / max(1, len(p["sections"]))))
        if params.get("feedback") and "length" in params["feedback"]:
            m = re.search(r"(\d+) words", params["feedback"])
            if m:
                per = int(per * ((lo + hi) / 2) / max(1, int(m.group(1))))
        doc = Document()
        st = doc.styles["Normal"]
        st.font.name, st.font.size = "Calibri", Pt(11)
        doc.add_heading(p["title"], 0)
        bodies = []
        for s in p["sections"]:
            text = job.ask_text("builder", "You write clear, plain business prose. No headings, no bullet lists, no em dashes.",
                                f"Document: {p['title']}\nRequest: {req}\n\nWrite the section '{s['heading']}' ({s.get('points', '')}). "
                                f"About {per} words, in 1 to 3 paragraphs." +
                                (" A table with the figures follows this text, so do not repeat every number." if p.get("table") and p["table"].get("section", "").lower() in s["heading"].lower() else ""),
                                max_tokens=int(per * 2.2) + 60, temperature=0.4)
            text = clean(re.sub(r"^#+.*\n|^\s*\*\*.*\*\*\s*$", "", text, flags=re.M)).strip()
            bodies.append(text)
            doc.add_heading(s["heading"], 1)
            for para in [x.strip() for x in re.split(r"\n\s*\n", text) if x.strip()]:
                doc.add_paragraph(para)
            t = p.get("table")
            if t and t.get("section") and t["section"].lower() in s["heading"].lower():
                table = doc.add_table(rows=1, cols=2)
                table.style = "Light Shading Accent 1"
                table.rows[0].cells[0].text, table.rows[0].cells[1].text = t["columns"]
                for name, val in t["rows"]:
                    c = table.add_row().cells
                    c[0].text, c[1].text = name, f"{val:,.0f}" if float(val).is_integer() else f"{val:,.2f}"
                if t.get("total"):
                    total = sum(v for _, v in t["rows"])
                    c = table.add_row().cells
                    c[0].text, c[1].text = "Total", f"{total:,.0f}" if float(total).is_integer() else f"{total:,.2f}"
        out = job.workspace / p["file"]
        doc.save(out)
        words = sum(len(re.findall(r"\b\w+\b", b)) for b in bodies)
        return Outcome(True, f"wrote {p['file']}: {len(p['sections'])} sections, about {words} words", {"file": p["file"], "words": words},
                       [p["file"]], made_by="model+template")

    def verify(self, job, params, outcome):
        ok = (job.workspace / outcome.result["file"]).exists()
        return Verdict(ok, [{"id": "file_written", "pass": ok, "detail": outcome.result["file"]}], "file exists")


class CheckDocument(Capability):
    name = "check_document"
    purpose = "Check a Word document: headings in order, length, table totals, no em dashes or placeholders"
    requires = {"binaries": [], "modules": ["docx"]}
    verification = "independent parse of the .docx file"
    domains = ("documents",)

    def run(self, job, params):
        return Outcome(True, "checked")

    def verify(self, job, params, outcome):
        from docx import Document
        p = job.state.task("outline")["result"]
        d = Document(job.workspace / p["file"])
        heads = [x.text.strip() for x in d.paragraphs if x.style.name.lower().startswith("heading") and x.style.name != "Title" and x.text.strip()]
        checks = [{"id": "headings_in_order", "pass": heads == [s["heading"] for s in p["sections"]], "detail": heads}]
        words = len(re.findall(r"\b\w+\b", "\n".join(x.text for x in d.paragraphs)))
        if p.get("words"):
            checks.append({"id": "length", "pass": p["words"][0] <= words <= p["words"][1], "detail": f"{words} words, wanted {p['words']}"})
        text = "\n".join(x.text for x in d.paragraphs)
        checks.append({"id": "no_em_dashes", "pass": not EM.search(text), "detail": ""})
        checks.append({"id": "no_placeholders", "pass": not re.search(r"lorem ipsum|\bTBD\b|\[insert|\[your", text, re.I), "detail": ""})
        if p.get("table"):
            ok = False
            for t in d.tables:
                cells = [[c.text for c in r.cells] for r in t.rows]
                nums = [float(r[1].replace(",", "")) for r in cells[1:] if r[0].lower() != "total" and re.match(r"^[\d,.]+$", r[1])]
                tot = [r for r in cells if r[0].lower() == "total"]
                ok = len(nums) == len(p["table"]["rows"]) and (not p["table"].get("total") or (tot and abs(float(tot[0][1].replace(",", "")) - sum(nums)) < 0.01))
            checks.append({"id": "table_correct", "pass": bool(ok), "detail": ""})
        ok = all(c["pass"] for c in checks)
        return Verdict(ok, checks, "python-docx parse", rework=None if ok else "write")   # fixed by rewriting, not here


CAPABILITIES = [PlanDocument(), WriteDocument(), CheckDocument()]
