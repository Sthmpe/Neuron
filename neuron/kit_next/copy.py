"""Rules for every piece of text NEURON shows: no em dashes, and none of the stock phrases that make
copy read as machine-written. Applied when text is rendered, so nothing slips through."""
import re

DASHES = re.compile(r"\s*(?:—|―|(?<=\s)--(?=\s)|(?<=\s)–(?=\s))\s*")
CLICHES = {
    r"\bunlock(s|ing)?\b": "get", r"\belevate(s|d)?\b": "improve", r"\bseamless(ly)?\b": "simple",
    r"\bempower(s|ing)?\b": "help", r"\bcutting[- ]edge\b": "modern", r"\bstate[- ]of[- ]the[- ]art\b": "modern",
    r"\bworld[- ]class\b": "excellent", r"\bnext[- ]level\b": "better", r"\bgame[- ]chang(er|ing)\b": "big step",
    r"\bsupercharge(s|d)?\b": "speed up", r"\brevolutioni[sz](e|es|ing)\b": "change", r"\bin today'?s fast[- ]paced world,?\s*": "",
    r"\blook no further\b[.!]?\s*": "", r"\bembark on\b": "start", r"\bdelve into\b": "explore", r"\bsynergy\b": "teamwork",
}


def no_dashes(text):
    """Em dashes (and dash look-alikes used as em dashes) become a comma, or vanish at the edges."""
    if not text:
        return text
    out = DASHES.sub(", ", text)
    out = re.sub(r"^\s*,\s*|\s*,\s*$", "", out)
    return re.sub(r",\s*,", ",", out)


def plain(text):
    """Swap stock phrases for plain words."""
    out = text
    for pattern, repl in CLICHES.items():
        out = re.sub(pattern, lambda m: _keep_case(m.group(0), repl), out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip()


def _keep_case(orig, repl):
    return repl[:1].upper() + repl[1:] if orig[:1].isupper() and repl else repl


def clean(text):
    return plain(no_dashes(text)) if isinstance(text, str) else text


def has_dash(text):
    return bool(re.search(r"—|―", text or ""))


def cliches(text):
    return [p for p in CLICHES if re.search(p, text or "", re.I)]
