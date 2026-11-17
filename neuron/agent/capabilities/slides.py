"""PowerPoint decks. Slide count and titles the owner listed are parsed by code; the model writes short
bullets; the design system supplies palette, fonts and layout; LibreOffice renders the deck to check it."""
import re
import tempfile
from pathlib import Path

from ...kit_next.copy import clean
from ..capability import Capability, Outcome, Verdict
from .sheets import soffice

EM = re.compile(r"[—―]")


def parse_request(req):
    out = {"file": (re.findall(r"\b([\w-]+\.pptx)\b", req) or ["deck.pptx"])[0]}
    m = re.search(r"(\d+)[- ]slide", req, re.I)
    out["count"] = int(m.group(1)) if m else None
    m = re.search(r"at most (\d+) bullet", req, re.I)
    out["max_bullets"] = int(m.group(1)) if m else 5
    m = re.search(r"slides?\s*:\s*(.+?)(?:\.\s+[A-Z]|$)", req, re.I | re.S)
    titles = []
    if m:
        for num, title in re.findall(r"(\d+)\s+([^,]+?)(?=,\s*\d+\s|$)", m.group(1).strip().rstrip(".")):
            titles.append(re.sub(r"^(title slide|title)\b.*", "Title", title.strip(), flags=re.I))
    out["titles"] = titles
    if out["count"] is None and titles:
        out["count"] = len(titles)
    return out


class PlanDeck(Capability):
    name = "plan_deck"
    purpose = "Plan a presentation: one title and a few short bullets per slide"
    permissions = ("use_model",)
    resources = {"ram_mb": 50, "uses_model": True}
    verification = "slide count and titles the owner asked for are kept; bullets stay within the limit"
    domains = ("documents",)

    def run(self, job, params):
        req = job.state.goal()["request"]
        fx = parse_request(req)
        n = fx["count"] or 6
        schema = {"type": "object", "required": ["name", "tagline", "slides"],
                  "properties": {"name": {"type": "string"}, "tagline": {"type": "string"},
                                 "slides": {"type": "array", "minItems": n - 1, "maxItems": n - 1, "items": {
                                     "type": "object", "required": ["title", "bullets"],
                                     "properties": {"title": {"type": "string"}, "bullets": {"type": "array", "minItems": 2,
                                                                                           "maxItems": fx["max_bullets"], "items": {"type": "string"}}}}}}}
        listed = [t for t in fx["titles"] if t != "Title"]
        hint = f"Use these slide titles in order: {', '.join(listed)}." if listed else ""
        data = job.ask_json("planner", "You plan clear, short presentations. Bullets are under 12 words, no em dashes.",
                            f"Request: {req}\n\nSlide 1 is the title slide (name and tagline). Plan the other {n - 1} slides. {hint}"
                            + (f"\nFix: {params['feedback']}" if params.get("feedback") else ""), schema, max_tokens=900)
        if not data:
            return Outcome(False, "the model gave no slide plan")
        slides = data["slides"][: n - 1]
        if listed:
            for s, t in zip(slides, listed):
                s["title"] = t
        for s in slides:
            s["bullets"] = [clean(b) for b in s["bullets"]][: fx["max_bullets"]]
        plan = {**fx, "count": n, "name": clean(data["name"]), "tagline": clean(data["tagline"]), "slides": slides}
        return Outcome(True, f"{n} slides: {data['name']}; " + ", ".join(s["title"] for s in slides), plan, made_by="model")

    def verify(self, job, params, outcome):
        p = outcome.result
        ok = len(p["slides"]) == p["count"] - 1 and all(1 <= len(s["bullets"]) <= p["max_bullets"] for s in p["slides"])
        return Verdict(ok, [{"id": "plan_shape", "pass": ok, "detail": f"{len(p['slides']) + 1} slides"}], "plan check")


class BuildDeck(Capability):
    name = "build_deck"
    purpose = "Build the .pptx with the design system's palette, fonts and layout"
    permissions = ("write_workspace",)
    requires = {"binaries": [], "modules": ["pptx"]}
    verification = "checked by check_deck"
    domains = ("documents",)

    def run(self, job, params):
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.util import Emu, Inches, Pt
        from ...design.engine import FONTS, choose
        p = job.state.task("outline")["result"]
        d = choose(job.state.goal()["request"], app_name=p["name"], avoid_history=False)
        t = d["tokens"]
        rgb = lambda h: RGBColor.from_string(h.lstrip("#").upper())
        head_font = FONTS[[f for f in d["fonts"] if FONTS[f][1] == "serif"][0] if any(FONTS[f][1] == "serif" for f in d["fonts"]) else d["fonts"][0]][0]
        body_font = FONTS[d["fonts"][-1]][0]
        pres = Presentation()
        pres.slide_width, pres.slide_height = Inches(13.333), Inches(7.5)
        W, H = pres.slide_width, pres.slide_height

        def fill_bg(slide, color):
            bg = slide.background.fill
            bg.solid()
            bg.fore_color.rgb = rgb(color)

        def style(par, size, color, font, bold=False):
            for r in par.runs:
                r.font.size, r.font.color.rgb, r.font.name, r.font.bold = Pt(size), rgb(color), font, bold

        s = pres.slides.add_slide(pres.slide_layouts[0])
        fill_bg(s, t["color-strong"])
        s.shapes.title.text = p["name"]
        s.shapes.title.left, s.shapes.title.top, s.shapes.title.width, s.shapes.title.height = Inches(0.9), Inches(2.4), W - Inches(1.8), Inches(1.6)
        style(s.shapes.title.text_frame.paragraphs[0], 54, t["color-on-strong"], head_font, True)
        sub = s.placeholders[1]
        sub.text = p["tagline"]
        sub.left, sub.top, sub.width, sub.height = Inches(0.9), Inches(4.1), W - Inches(1.8), Inches(1.0)
        style(sub.text_frame.paragraphs[0], 24, t["color-on-strong-muted"], body_font)
        for i, sl in enumerate(p["slides"], 2):
            s = pres.slides.add_slide(pres.slide_layouts[5])
            fill_bg(s, t["color-bg"])
            bar = s.shapes.add_shape(1, Inches(0.9), Inches(0.9), Inches(0.5), Emu(57150))
            bar.fill.solid()
            bar.fill.fore_color.rgb = rgb(t["color-action"])
            bar.line.fill.background()
            ti = s.shapes.title
            ti.text = sl["title"]
            ti.left, ti.top, ti.width, ti.height = Inches(0.9), Inches(1.05), W - Inches(1.8), Inches(1.1)
            style(ti.text_frame.paragraphs[0], 36, t["color-heading"], head_font, True)
            box = s.shapes.add_textbox(Inches(0.9), Inches(2.4), W - Inches(1.8), H - Inches(3.2))
            tf = box.text_frame
            tf.word_wrap = True
            size = 24 if len(sl["bullets"]) <= 4 else 20
            for k, b in enumerate(sl["bullets"]):
                par = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                par.text = "•  " + b
                par.space_after = Pt(14)
                style(par, size, t["color-ink"], body_font)
            num = s.shapes.add_textbox(W - Inches(1.4), H - Inches(0.8), Inches(0.6), Inches(0.4))
            num.text_frame.text = str(i)
            style(num.text_frame.paragraphs[0], 14, t["color-ink-muted"], body_font)
        out = job.workspace / p["file"]
        pres.save(out)
        return Outcome(True, f"built {p['file']} ({p['count']} slides, palette {d['palette']['name']})", {"file": p["file"], "palette": d["palette"]["name"]},
                       [p["file"]], made_by="template")


class CheckDeck(Capability):
    name = "check_deck"
    purpose = "Render the deck in a presentation application and check count, titles, bullets and wording"
    requires = {"binaries": ["soffice"], "modules": ["pptx", "pypdf"]}
    verification = "LibreOffice renders every slide; independent parse of the .pptx"
    domains = ("documents",)

    def run(self, job, params):
        p = job.state.task("outline")["result"]
        out = Path(tempfile.mkdtemp(prefix="render-"))
        soffice(["--convert-to", "pdf", "--outdir", str(out), str(job.workspace / p["file"])])
        pdf = out / (Path(p["file"]).stem + ".pdf")
        pages = 0
        if pdf.exists():
            from pypdf import PdfReader
            pages = len(PdfReader(pdf).pages)
            (job.workspace / ".neuron" / "job").mkdir(parents=True, exist_ok=True)
            pdf.replace(job.workspace / ".neuron" / "job" / "deck_render.pdf")
        return Outcome(True, f"rendered {pages} pages", {"pages": pages})

    def verify(self, job, params, outcome):
        from pptx import Presentation
        p = job.state.task("outline")["result"]
        pres = Presentation(job.workspace / p["file"])
        text = "\n".join(sh.text_frame.text for s in pres.slides for sh in s.shapes if sh.has_text_frame)
        checks = [{"id": "slide_count", "pass": len(pres.slides) == p["count"], "detail": len(pres.slides)},
                  {"id": "renders", "pass": outcome.result["pages"] == p["count"], "detail": outcome.result["pages"]},
                  {"id": "titles", "pass": all(s.shapes.title is not None and s.shapes.title.text.strip() for s in pres.slides), "detail": ""},
                  {"id": "no_em_dashes", "pass": not EM.search(text), "detail": ""}]
        return Verdict(all(c["pass"] for c in checks), checks, "LibreOffice render + python-pptx parse")


CAPABILITIES = [PlanDeck(), BuildDeck(), CheckDeck()]
