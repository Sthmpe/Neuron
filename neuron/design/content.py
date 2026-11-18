"""Content quality: what a careful editor rejects before a client ever sees a page, slide or document.

check(pieces, request) -> problems, each {"kind", "where", "detail"}. pieces = [(where, text), ...].
  placeholder  template text left behind: lorem ipsum, [Your name], {{name}}, TODO, "Company Name", example.com
  filler       stock phrases that say nothing ("we are passionate about", "top-notch service", "one-stop shop")
  repetition   the same sentence twice, or one phrase of four or more words used three or more times
  duplicate    the same heading twice, or two parts that say nearly the same thing
  invented     a testimonial, statistic, credential, opening hours or contact detail the owner did not give.
               NEURON may only state such facts when they are in the owner's request or files.
Everything here is rules, so a 1.5-billion-parameter model is held to the same standard as a large one.
"""
import re

PLACEHOLDER = re.compile(
    r"lorem ipsum|dolor sit amet|\[[^\]]{0,30}(your|name|insert|company|business|address|phone|email)[^\]]{0,30}\]|\{\{[^}]*\}\}|"
    r"\bTODO\b|\bTBD\b|\bXXX\b|\binsert (your|the|a) \w+|\byour (company|business|brand) name\b|\bcompany name\b|"
    r"\bbusiness name\b|\bexample\.(com|org)\b|\b555[- ]\d{4}\b|\bplaceholder\b|\bsample text\b|\bcoming soon\b", re.I)
FILLER = [r"\bwe are passionate about\b", r"\bpassionate about (what we do|delivering|providing)\b", r"\btop[- ]notch\b",
          r"\bone[- ]stop[- ]shop\b", r"\bsecond to none\b", r"\bunparalleled\b", r"\bbest[- ]in[- ]class\b",
          r"\bcustomer satisfaction is our (top )?priority\b", r"\byour satisfaction is (our|guaranteed)\b",
          r"\bwe pride ourselves\b", r"\bcommitted to excellence\b", r"\bexceed(s|ing)? (your|all) expectations\b",
          r"\bhigh[- ]quality (service|services|products) at (affordable|competitive) prices\b", r"\bwe go the extra mile\b",
          r"\btailored to (meet )?your (unique )?needs\b", r"\bdedicated team of (experienced )?professionals\b",
          r"\bwe are here to help\b", r"\bdon'?t hesitate to (contact|reach out)\b", r"\bwhat are you waiting for\b",
          r"\bthe best (service|quality|experience) (in town|around|possible)\b", r"\bnothing but the best\b",
          r"\bquality you can trust\b", r"\bexcellence in every\b", r"\bwhere (quality|excellence) meets\b",
          r"\bunlock\b", r"\belevate\b", r"\bseamless\b", r"\bcutting[- ]edge\b", r"\bworld[- ]class\b"]
FILLER_RE = re.compile("|".join(FILLER), re.I)

TESTIMONIAL = re.compile(r"[\"“][^\"”]{25,}[\"”]\s*(?:[-–—,]\s*)?[A-Z][a-z]+|\btestimonials?\b|\bwhat our (clients|customers|guests) say\b|"
                         r"\b(five|5)[- ]stars?\b|★|\brated \d|\b\d(\.\d)? out of 5\b|\breviews?\b(?! (our|your|the) )", re.I)
STATISTIC = re.compile(r"\b\d[\d,.]*\s*(%|percent\b|\+)|\b(over|more than|nearly|almost|thousands of|hundreds of)\s+\d[\d,.]*(\s+(years?|clients?|customers?|cases?|families|projects?))?|"
                       r"\b\d[\d,]*\s+(years?|clients?|customers?|cases?|happy|satisfied|families|projects?|awards?|weddings?)\b|"
                       r"\b(thousands|hundreds) of (happy |satisfied )?(clients|customers|families)\b|#\s?1\b|\bnumber one\b", re.I)
CREDENTIAL = re.compile(r"\baward[- ]winning\b|\bcertified\b|\blicen[cs]ed\b|\baccredited\b|\bboard[- ]certified\b|\bregistered with\b|"
                        r"\bmember of the\b|\bfellow of\b|\bqualified\b|\bdecades? of experience\b|\byears of experience\b|"
                        r"\bexperienced\b|\bexperts?\b|\bspecialists?\b|\bleading\b|\btrusted by\b|\bfeatured in\b|\bas seen (on|in)\b", re.I)
HOURS = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b|\b\d{1,2}:\d{2}\b|\bopen (daily|every day|7 days|seven days|24/7|24 hours)\b|"
                   r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\s*(-|–|to|through)\s*(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b|\b24/7\b", re.I)
CONTACT = re.compile(r"\+?\d[\d ()-]{7,}\d|[\w.+-]+@[\w-]+\.[\w.]+|\bwww\.[\w-]+\.\w+|https?://\S+|"
                     r"\b\d+[a-z]?,?\s+[A-Z][\w']*(\s+[A-Z][\w']*)?\s+(street|st|road|rd|avenue|ave|close|crescent|way|lane|drive|boulevard)\b",
                     re.I)
INVENTED = [("testimonial", TESTIMONIAL), ("statistic", STATISTIC), ("credential", CREDENTIAL), ("opening hours", HOURS),
            ("contact detail", CONTACT)]


OWNER_FACTS = [
    ("price", re.compile(r"(?:₦|\$|£|€)\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s*(?:naira|kobo|dollars?|pounds?|euros?)\b", re.I)),
    ("duration", re.compile(r"\b\d+\s*(?:minutes?|mins?|hours?|days?|weeks?)\b", re.I)),
    ("time", re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.I)),
    ("days", re.compile(r"\b(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\s*(?:to|-|–|through)\s*"
                        r"(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b|\bevery day\b", re.I)),
    ("address", re.compile(r"\b(?:[Pp]lot\s+)?\d+[a-z]?,?\s+[A-Z][\w']+(?:\s+[A-Z][\w']+)*\s+(?i:street|road|avenue|crescent|close|way|lane|drive|boulevard)\b")),
]


def owner_facts(request):
    """The concrete facts the owner gave (prices, durations, times, days, addresses): a page must show them all."""
    out = []
    for kind, rx in OWNER_FACTS:
        for m in rx.finditer(request or ""):
            if m.group(0) not in [f for _, f in out]:
                out.append((kind, m.group(0).strip()))
    return out


def _shown(fact, kind, text):
    t = _norm(text).replace(",", "")
    if kind in ("price", "duration", "time", "address"):
        nums = re.findall(r"\d+", fact.replace(",", ""))
        if not all(re.search(rf"(?<!\d){n}(?!\d)", t) for n in nums):
            return False
        if kind == "address":                    # the street name too, not just the number
            name = re.sub(r"^(plot\s+)?\d+[a-z]?,?\s+", "", fact, flags=re.I).lower()
            return name.split()[0] in t
        return True
    days = re.findall(r"mon|tue|wed|thu|fri|sat|sun|every day", fact.lower())
    return all(d in t for d in days)


def missing_facts(request, pieces):
    text = " ".join(t or "" for _, t in pieces)
    return [{"kind": "missing", "where": "page", "type": k, "fact": f, "detail": f"the owner's {k} '{f}' is not on the page"}
            for k, f in owner_facts(request) if not _shown(f, k, text)]


STOP = set("this that with from have will your their they them were what when where which about into over make made website "
           "page site want need please also only each every them show give like just very more most some such than then".split())


def vague_hero(spec, request):
    """The line under the headline must name something of this business (what it sells or does, or where)."""
    sub = ((spec.get("home") or {}).get("subheadline") or "").lower()
    req = {w[:5] for w in re.findall(r"[a-z]{4,}", (request or "").lower()) if w not in STOP}
    words = {w[:5] for w in re.findall(r"[a-z]{4,}", sub) if w not in STOP}
    if sub and not (words & req):
        return [{"kind": "vague", "where": "hero:text", "detail": f"the line under the headline ('{sub[:60]}') names nothing from the request"}]
    return []


def thin_items(spec):
    out = []
    for sec in (spec.get("home") or {}).get("sections") or []:
        empty = [it.get("title", "") for it in sec.get("items") or [] if not (it.get("text") or "").strip()]
        if empty:
            out.append({"kind": "thin", "where": sec.get("title", "section"),
                        "detail": f"the items in '{sec.get('title', '')}' have no words ({', '.join(empty[:4])})"})
    return out


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").lower()).strip()


def _given(fact, request):
    """A fact is the owner's if its numbers (or, without numbers, its key words) appear in what the owner gave."""
    req = _norm(request)
    req_numbers = set(re.findall(r"\d+", req.replace(",", "")))
    req_digits = re.sub(r"\D", "", req)
    whole = re.sub(r"\D", "", fact)
    if len(whole) >= 7:                         # a phone number written with different spacing is the same number
        return whole in req_digits
    digits = re.findall(r"\d+", fact.replace(",", ""))
    if digits:
        return all(d in req_numbers for d in digits)
    words = [w for w in re.findall(r"[a-z]+", fact.lower()) if len(w) > 3]
    return bool(words) and all(w[:6] in req for w in words)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) > 3]


def _shingles(text, n=3):
    w = re.findall(r"[a-z0-9']+", text.lower())
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def check(pieces, request=""):
    problems = []
    seen_sentences = {}
    for where, text in pieces:
        for m in PLACEHOLDER.finditer(text or ""):
            problems.append({"kind": "placeholder", "where": where, "detail": f"leftover template text '{m.group(0)}'"})
        for m in FILLER_RE.finditer(text or ""):
            problems.append({"kind": "filler", "where": where, "detail": f"stock phrase '{m.group(0)}' says nothing specific"})
        for kind, rx in INVENTED:
            for m in rx.finditer(text or ""):
                if kind == "testimonial" and re.match(r"reviews?$", m.group(0), re.I) and "review" in _norm(request):
                    continue
                if not _given(m.group(0), request):
                    problems.append({"kind": "invented", "where": where, "type": kind, "fact": m.group(0).strip(),
                                     "detail": f"{kind} '{m.group(0).strip()}' was not given by the owner"})
        for s in sentences(text):
            key = _norm(re.sub(r"[^\w\s]", "", s))
            if len(key.split()) >= 6:               # short headings and button words may repeat; sentences may not
                if key in seen_sentences and seen_sentences[key] != where:
                    problems.append({"kind": "repetition", "where": where, "detail": f"sentence repeated from {seen_sentences[key]}: '{s[:80]}'"})
                seen_sentences.setdefault(key, where)
    all_text = " ".join(t or "" for _, t in pieces).lower()
    words = re.findall(r"[a-z0-9']+", all_text)
    counts = {}
    for i in range(len(words) - 3):
        g = " ".join(words[i:i + 4])
        counts[g] = counts.get(g, 0) + 1
    req = _norm(request)
    for g, c in sorted(counts.items(), key=lambda x: -x[1]):
        if c >= 3 and g not in req and not re.fullmatch(r"(the|a|an|and|of|to|in|for|on|with|your|our|we|you|is|are|it)( \S+){3}", g):
            problems.append({"kind": "repetition", "where": "page", "detail": f"phrase '{g}' used {c} times"})
            break
    heads = [(w, t) for w, t in pieces if w.endswith(":title")]
    seen = {}
    for w, t in heads:
        k = _norm(t)
        if k in seen:
            problems.append({"kind": "duplicate", "where": w, "detail": f"heading '{t}' appears twice"})
        seen[k] = w
    bodies = {}
    for w, t in pieces:
        sec = w.split(":")[0]
        if not w.endswith(":title"):
            bodies[sec] = bodies.get(sec, "") + " " + (t or "")
    names = list(bodies)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa, sb = _shingles(bodies[a]), _shingles(bodies[b])
            if len(sa) >= 6 and len(sb) >= 6 and len(sa & sb) / min(len(sa), len(sb)) > 0.5:
                problems.append({"kind": "duplicate", "where": b, "detail": f"says nearly the same as {a}"})
    return problems


def spec_pieces(spec):
    """The words of a planned site, labelled by where they appear."""
    h = spec.get("home") or {}
    out = [("hero:title", h.get("headline", "")), ("hero:text", h.get("subheadline", ""))]
    for i, sec in enumerate(h.get("sections") or []):
        out.append((f"section{i + 1}:title", sec.get("title", "")))
        if sec.get("text"):
            out.append((f"section{i + 1}:text", sec["text"]))
        for j, it in enumerate(sec.get("items") or []):
            out.append((f"section{i + 1}:item{j + 1}", f"{it.get('title', '')}. {it.get('text', '')}"))
    for i, f in enumerate(spec.get("forms") or []):
        out.append((f"form{i + 1}:title", f.get("title", "")))
        out.append((f"form{i + 1}:text", f.get("thanks", "")))
    return out


def remove_invented(spec, request):
    """Last resort after the planner was told and still invented facts: drop the sentences that state them.
    Returns the plain descriptions of what was removed (recorded as decisions, never hidden)."""
    removed = []

    def strip(text, where):
        keep = []
        for s in sentences(text):
            bad = [m.group(0) for kind, rx in INVENTED for m in rx.finditer(s) if not _given(m.group(0), request)]
            if bad:
                removed.append(f"{where}: '{s[:90]}' (states {', '.join(bad[:2])}, not given by the owner)")
            else:
                keep.append(s)
        return " ".join(keep)

    h = spec.get("home") or {}
    h["subheadline"] = strip(h.get("subheadline", ""), "subheadline")
    kept = []
    for sec in h.get("sections") or []:
        if TESTIMONIAL.search(sec.get("title", "")) and not _given(sec["title"], request):
            removed.append(f"section '{sec['title']}' (reviews or testimonials the owner did not give)")
            continue
        kept.append(sec)
    h["sections"] = kept
    for sec in h.get("sections") or []:
        sec["text"] = strip(sec.get("text", ""), sec.get("title", "section"))
        items = []
        for it in sec.get("items") or []:
            had_text = bool(it.get("text"))
            it["text"] = strip(it.get("text", ""), it.get("title", "item"))
            if had_text and not it["text"]:              # it only existed to state the invented fact
                continue
            bad_title = [m.group(0) for kind, rx in INVENTED for m in rx.finditer(it.get("title", "")) if not _given(m.group(0), request)]
            if bad_title:
                removed.append(f"item '{it['title']}' (states {bad_title[0]}, not given by the owner)")
                continue
            items.append(it)
        sec["items"] = items
    h["sections"] = [s for s in h.get("sections") or [] if s.get("text") or s.get("items")]
    return removed


def feedback(problems, limit=8):
    """Problems as plain instructions for the planner's next attempt."""
    lines = []
    for p in problems[:limit]:
        if p["kind"] == "missing":
            lines.append(f"- add the owner's {p['type']} \"{p['fact']}\" exactly as given (in a section's text or an item).")
        elif p["kind"] == "vague":
            lines.append(f"- {p['detail']}: say what this business sells or does, or where, using the owner's words.")
        elif p["kind"] == "thin":
            lines.append(f"- {p['detail']}: give each item one short, specific line about this business.")
        elif p["kind"] == "invented":
            lines.append(f"- {p['where']}: remove the {p['type']} \"{p['fact']}\": the owner did not give it. Only state facts the owner gave.")
        elif p["kind"] == "placeholder":
            lines.append(f"- {p['where']}: replace the {p['detail']} with real words about this business.")
        elif p["kind"] == "filler":
            lines.append(f"- {p['where']}: replace the {p['detail']} with something concrete the owner said.")
        else:
            lines.append(f"- {p['where']}: {p['detail']}; say something different or drop it.")
    return "\n".join(lines)
