"""Colour words people actually use, and finding them in a request."""
import re

from .color import parse_hex, to_hex

NAMED = {
    "black": "#111111", "white": "#ffffff", "grey": "#808080", "gray": "#808080", "charcoal": "#36454f",
    "silver": "#b8bcc2", "red": "#d62828", "crimson": "#b5122e", "scarlet": "#e0301e", "burgundy": "#7a1f2b",
    "maroon": "#7b1e2b", "wine": "#6f1d32", "oxblood": "#5e1a1d", "cherry": "#c2185b", "rose": "#e0607e",
    "pink": "#e8749a", "blush": "#e9b8b8", "coral": "#f26b5b", "salmon": "#f08a6c", "orange": "#f07c1d",
    "tangerine": "#f28c28", "peach": "#f6b48f", "apricot": "#f5a65b", "amber": "#f0a202", "terracotta": "#c2603e",
    "rust": "#b4532a", "copper": "#b8733b", "bronze": "#a0703a", "brown": "#7b4a2d", "chocolate": "#5b3a29",
    "coffee": "#6f4e37", "caramel": "#c1803e", "tan": "#c9a27a", "beige": "#e3d5bf", "cream": "#f3ead8",
    "ivory": "#f7f2e5", "sand": "#d9c5a0", "khaki": "#b5a77a", "gold": "#c9a227", "golden": "#d4a017",
    "mustard": "#d4a32a", "yellow": "#f4c430", "lemon": "#f2d43b", "lime": "#a3d12b", "olive": "#6b7a2e",
    "green": "#2f8f4e", "emerald": "#11845b", "forest": "#24543a", "forest green": "#24543a", "moss": "#5a6e3a",
    "sage": "#8fa98a", "mint": "#7fd1ae", "jade": "#17876b", "teal": "#0f7c80", "turquoise": "#1fb5b0",
    "aqua": "#33c4d6", "cyan": "#13a6c9", "sky": "#4ba3e3", "sky blue": "#4ba3e3", "light blue": "#7db8e8",
    "baby blue": "#9ccbef", "blue": "#2563c9", "royal blue": "#2747c4", "cobalt": "#1f4fbf", "azure": "#2a7fd6",
    "navy": "#1b2a4a", "navy blue": "#1b2a4a", "midnight": "#16213e", "midnight blue": "#16213e", "indigo": "#3f3a9e",
    "purple": "#6d3fb8", "violet": "#7b4fd1", "lavender": "#a99bd8", "lilac": "#b9a2d8", "plum": "#6a2c5a",
    "magenta": "#c2187a", "fuchsia": "#c026a3", "slate": "#4a5768", "steel": "#58708a", "graphite": "#3b3f45",
}
NAMED.update({"moss green": "#5a6e3a", "royal blue": "#2747c4", "sage green": "#8fa98a", "olive green": "#6b7a2e", "bottle green": "#1f5a3d", "hunter green": "#2d5a3d",
              "burnt orange": "#cc5500", "dusty pink": "#d4a5a5", "dusty rose": "#c9898f", "rose gold": "#c9908a",
              "champagne": "#e9d8b4", "off white": "#f6f3ec", "off-white": "#f6f3ec", "brick": "#a8442a",
              "ochre": "#c7882b", "honey": "#e0a340", "espresso": "#4b2e22", "denim": "#3b5f8a", "petrol": "#1d5c69",
              "sea green": "#2e8b6e", "pine": "#2b5d45", "clay": "#b9785a", "linen": "#efe6d8", "stone": "#a8a29a"})
AMBIGUOUS = {"gold", "rose", "olive", "orange", "lemon", "lime", "coffee", "chocolate", "caramel", "cherry", "peach",
             "apricot", "cream", "wine", "salmon", "mint", "plum", "sage", "honey", "sand", "tan", "moss", "espresso",
             "linen", "stone", "clay", "brick", "pine", "silver", "copper", "bronze", "amber", "sky", "slate", "steel",
             "coral", "jade", "rust", "denim", "champagne", "ivory", "black", "white"}
MODIFIERS = {"dark": (-0.16, 1.0), "deep": (-0.12, 1.1), "light": (0.14, 0.7), "pale": (0.2, 0.45),
             "bright": (0.03, 1.3), "soft": (0.1, 0.6), "dusty": (0.04, 0.5), "muted": (0.0, 0.5), "rich": (-0.06, 1.15)}
COLOUR_TALK = re.compile(r"colou?r|tones?\b|palette|brand|theme|shades?\b|accent|background|scheme")
HEXWORD = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")


def _apply_modifier(hexv, mod):
    from .color import hex_to_oklch, oklch_to_hex
    dl, cm = MODIFIERS[mod]
    L, C, H = hex_to_oklch(hexv)
    return oklch_to_hex((max(0.15, min(0.97, L + dl)), C * cm, H))


JOINERS = {"and", "with", "or", "plus", "&", "on", "a", "touch", "of", "bit", "some"} | set(MODIFIERS)


def _joined(text, a, b):
    """True when two colour words are joined only by small words ('black with bright orange', 'navy and gold')."""
    first, second = (a, b) if a["start"] < b["start"] else (b, a)
    between = re.findall(r"[a-z&]+", text[first["end"]: second["start"]])
    return len(between) <= 4 and all(w in JOINERS for w in between)


def _in_a_name(original, start, end):
    """True when a capitalised colour word sits next to another capitalised word mid-sentence."""
    word = original[start:end]
    if not word[:1].isupper():
        return False
    before = original[:start].rstrip()
    after = original[end:].lstrip()
    sentence_start = not before or before[-1] in ".!?:\n"
    next_cap = bool(re.match(r"[A-Z][a-z]", after))
    prev_cap = bool(re.search(r"\b[A-Z][a-z]+$", before)) and not sentence_start
    return next_cap or prev_cap


def find_colours(request):
    """Colours the owner asked for, in the order they appear. Plain colour words always count. Words that
    are also foods or materials ('lemon cake', 'olive oil', 'gold jewellery') count only when the request
    talks about colour near them, or they sit right next to another colour ('navy and gold').
    'dark', 'pale', 'dusty' and similar words in front adjust the colour."""
    text = request.lower()
    hits = []
    for m in HEXWORD.finditer(request):
        hits.append({"start": m.start(), "end": m.end(), "word": m.group(0), "hex": to_hex(parse_hex(m.group(0))), "sure": True})
    taken = [(h["start"], h["end"]) for h in hits]
    for name in sorted(NAMED, key=len, reverse=True):
        for m in re.finditer(rf"\b{re.escape(name)}\b", text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            if _in_a_name(request, m.start(), m.end()):
                continue          # "Golden Crust", "Green Acres": part of a business name, not a colour request
            hits.append({"start": m.start(), "end": m.end(), "word": name, "hex": NAMED[name],
                         "sure": name not in AMBIGUOUS})
    hits.sort(key=lambda h: h["start"])
    keep = []
    for i, h in enumerate(hits):
        if not h["sure"]:
            lo = max(text.rfind(".", 0, h["start"]), text.rfind("!", 0, h["start"]), text.rfind("?", 0, h["start"])) + 1
            hi = min([i for i in (text.find(".", h["end"]), text.find("!", h["end"]), text.find("?", h["end"])) if i >= 0] or [len(text)])
            window = text[max(lo, h["start"] - 30): min(hi, h["end"] + 30)]      # colour talk must be in the same sentence
            near = any(o is not h and _joined(text, h, o) for o in hits)
            if not (COLOUR_TALK.search(window) or near):
                continue
        before = text[max(0, h["start"] - 8): h["start"]].split()
        mod = before[-1] if before and before[-1] in MODIFIERS else None
        word = f"{mod} {h['word']}" if mod else h["word"]
        hexv = _apply_modifier(h["hex"], mod) if mod else h["hex"]
        keep.append({"word": word, "hex": hexv})
    out, seen = [], set()
    for k in keep:
        if k["hex"] not in seen:
            seen.add(k["hex"])
            out.append(k)
    return out[:4]
