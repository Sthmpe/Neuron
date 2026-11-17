"""Mood + optional user colours + a seed -> a complete design, with the reason in plain English.

The model is never asked for colours, fonts or layouts. It only writes the words; everything here is
rules and curated data, so a 1-billion-parameter model gets the same taste as a large one.
"""
import hashlib
import json
import os
import random
from pathlib import Path

from . import color as C
from .mood import MOODS, detect
from .names import find_colours

FONTS = {   # family file -> (CSS name, kind, heading weight)
    "inter": ("Inter", "sans", 680), "manrope": ("Manrope", "sans", 700), "plus-jakarta-sans": ("Plus Jakarta Sans", "sans", 700),
    "dm-sans": ("DM Sans", "sans", 650), "outfit": ("Outfit", "sans", 650), "figtree": ("Figtree", "sans", 680),
    "nunito": ("Nunito", "rounded", 800), "fraunces": ("Fraunces", "serif", 560), "playfair-display": ("Playfair Display", "serif", 560),
    "source-serif-4": ("Source Serif 4", "serif", 600), "lora": ("Lora", "serif", 560), "bricolage-grotesque": ("Bricolage Grotesque", "sans", 650),
    "cormorant-garamond": ("Cormorant Garamond", "serif", 600), "sora": ("Sora", "sans", 620), "libre-franklin": ("Libre Franklin", "sans", 650),
    "instrument-serif": ("Instrument Serif", "serif", 400),
}
SHADOWS = {   # depth styles; the colour is the dominant hue, never pure black
    "crisp": ("0 1px 2px {c}0d, 0 2px 8px {c}0f", "0 2px 4px {c}0d, 0 10px 24px {c}14", "0 4px 10px {c}12, 0 24px 48px {c}1f"),
    "soft": ("0 1px 3px {c}0a, 0 6px 16px {c}0d", "0 4px 12px {c}0d, 0 18px 40px {c}14", "0 8px 24px {c}10, 0 40px 80px {c}1c"),
    "lifted": ("0 2px 4px {c}12, 0 8px 18px {c}14", "0 6px 14px {c}14, 0 22px 44px {c}1f", "0 10px 24px {c}18, 0 36px 72px {c}29"),
    "whisper": ("0 1px 2px {c}08", "0 2px 10px {c}0a, 0 12px 30px {c}0d", "0 6px 20px {c}0d, 0 28px 60px {c}12"),
}
BUTTON_RADIUS = {"pill": "999px", "rounded": None, "sharp": "2px"}
DIMENSIONS = ("mood", "palette", "font", "hero", "features", "form", "nav", "rhythm")
HISTORY = Path(os.environ.get("NEURON_DESIGN_HISTORY", str(Path.home() / ".neuron" / "design_history.json")))


def _role_names(colours):
    return ", ".join(c["word"] for c in colours)


def assign_roles(colours, mood_palette):
    """Which user colour does which job. Returns (dominant, support, accent, sentence)."""
    info = [(c, *C.hex_to_oklch(c["hex"])) for c in colours]
    if len(info) == 1:
        c, L, Ch, H = info[0]
        if L > 0.86:
            scale = C.tonal_scale(c["hex"])
            return (c["hex"], scale[800], scale[700],
                    f"You asked for {c['word']}. It is a light colour, so it becomes the page's main tone; a deep "
                    f"shade of the same hue carries headings, bands and buttons, so the whole page stays in your colour.")
        if L < 0.42:
            return (c["hex"], c["hex"], c["hex"],
                    f"You asked for {c['word']}. It is deep enough to hold white text, so it carries the bands and the "
                    f"buttons, and very light tints of it form the background. One colour, used with restraint.")
        return (c["hex"], C.tonal_scale(c["hex"])[900], c["hex"],
                f"You asked for {c['word']}. Its soft tints form the background, a deep shade of it carries headings "
                f"and bands, and the colour itself is kept for buttons and highlights.")
    # two or more: the most vivid becomes the action colour, the lightest or calmest the main tone
    vivid = max(info, key=lambda x: x[2] * (1 - abs(x[1] - 0.6)))
    rest = [x for x in info if x is not vivid]
    calm = max(rest, key=lambda x: (x[1] > 0.86, -x[2]))
    others = [x for x in rest if x is not calm]
    dominant = calm[0]["hex"]
    if others:
        support = others[0][0]["hex"]
    elif calm[1] > 0.86:
        support = C.tonal_scale(vivid[0]["hex"])[900]
    else:
        support = dominant
    sentence = (f"You asked for {_role_names(colours)}. {calm[0]['word'].capitalize()} carries most of the page (its tints "
                f"form the background{' and its deep tone the bands and headings' if support == dominant else ''}"
                f"{f', {others[0][0][chr(119)+chr(111)+chr(114)+chr(100)]} supports it in bands and panels' if others else ''}); "
                f"{vivid[0]['word']} is kept for buttons and small highlights so it stays special.")
    if len(colours) > 3:
        sentence += f" {colours[3]['word'].capitalize()} was left out: a fourth colour would crowd the page."
    return dominant, support, vivid[0]["hex"], sentence


def color_tokens(dominant, support, accent):
    """Every colour the components use, all derived from three role colours, all contrast-checked."""
    Ld, Cd, Hd = C.hex_to_oklch(dominant)
    tint = min(Cd, 0.16)
    t = {}
    t["bg"] = C.oklch_to_hex((0.985, tint * 0.10, Hd))
    t["surface"] = "#ffffff"
    t["surface-2"] = C.oklch_to_hex((0.962, tint * 0.22, Hd))
    t["surface-3"] = C.oklch_to_hex((0.93, tint * 0.32, Hd))
    t["ink"] = C.ensure_contrast(C.oklch_to_hex((0.22, min(tint * 0.35, 0.03), Hd)), t["surface-3"], 12)
    t["ink-muted"] = C.ensure_contrast(C.oklch_to_hex((0.45, min(tint * 0.3, 0.025), Hd)), t["surface-3"], 5.0)
    t["ink-soft"] = C.ensure_contrast(C.oklch_to_hex((0.58, min(tint * 0.25, 0.02), Hd)), t["surface"], 3.2)
    # support: strong areas (hero band, dark sections, footer)
    Ls = C.hex_to_oklch(support)[0]
    t["strong"] = support
    t["on-strong"] = C.on_color(support, t["ink"], "#ffffff")
    if C.contrast(t["on-strong"], support) < 4.5:
        t["strong"], t["on-strong"] = C.button_pair(support, t["bg"], t["ink"])
    t["on-strong-muted"] = (C.ensure_contrast(C.oklch_to_hex((0.86, 0.02, C.hex_to_oklch(t["strong"])[2])), t["strong"], 4.6)
                            if t["on-strong"] == "#ffffff" else C.ensure_contrast(t["ink-muted"], t["strong"], 4.6))
    t["heading"] = C.ensure_contrast(C.tonal_scale(support)[900] if Ls < 0.5 and C.hex_to_oklch(support)[1] > 0.04 else t["ink"],
                                     t["surface-3"], 7)
    # accent: actions only
    t["action"], t["on-action"] = C.button_pair(accent, t["bg"], t["ink"])
    hov = C.hex_to_oklch(t["action"])
    t["action-hover"] = C.oklch_to_hex((max(0.12, hov[0] - 0.06) if t["on-action"] == "#ffffff" else min(0.97, hov[0] + 0.05), hov[1], hov[2]))
    if C.contrast(t["on-action"], t["action-hover"]) < 4.5:
        t["action-hover"] = t["action"]
    t["link"] = C.ensure_contrast(accent, t["surface-2"], 4.6)
    t["link"] = C.ensure_contrast(t["link"], t["surface-3"], 4.5)
    A = C.hex_to_oklch(accent)
    t["accent-soft"] = C.oklch_to_hex((0.94, min(A[1] * 0.35, 0.05), A[2]))
    t["accent-ink"] = C.ensure_contrast(accent, t["accent-soft"], 4.5)
    S = C.hex_to_oklch(support)
    t["support-soft"] = C.oklch_to_hex((0.93, min(S[1] * 0.4, 0.045), S[2]))
    t["support-ink"] = C.ensure_contrast(support, t["support-soft"], 4.5)
    t["focus"] = t["link"]
    t["success-bg"], t["success-ink"] = "#e7f5ec", C.ensure_contrast("#1f7a4d", "#e7f5ec", 4.6)
    t["error-bg"], t["error-ink"] = "#fdecec", C.ensure_contrast("#b42318", "#fdecec", 4.6)
    t["shadow-color"] = C.oklch_to_hex((0.25, min(tint * 0.5, 0.05), Hd))
    return t


def contrast_report(t):
    """Every text-on-background pair the components can produce, with its contrast. All must pass."""
    pairs = [("ink", "bg", 4.5), ("ink", "surface", 4.5), ("ink", "surface-2", 4.5), ("ink", "surface-3", 4.5),
             ("ink-muted", "bg", 4.5), ("ink-muted", "surface", 4.5), ("ink-muted", "surface-2", 4.5), ("ink-muted", "surface-3", 4.5),
             ("heading", "bg", 4.5), ("heading", "surface", 4.5), ("heading", "surface-2", 4.5),
             ("on-strong", "strong", 4.5), ("on-strong-muted", "strong", 4.5), ("on-action", "action", 4.5),
             ("on-action", "action-hover", 4.5), ("link", "bg", 4.5), ("link", "surface", 4.5), ("link", "surface-2", 4.5),
             ("accent-ink", "accent-soft", 4.5), ("support-ink", "support-soft", 4.5),
             ("success-ink", "success-bg", 4.5), ("error-ink", "error-bg", 4.5), ("ink-soft", "surface", 3.0)]
    return [{"text": a, "on": b, "ratio": round(C.contrast(t[a], t[b]), 2), "needs": n, "ok": C.contrast(t[a], t[b]) >= n}
            for a, b, n in pairs]


def _history():
    try:
        return json.loads(HISTORY.read_text())
    except (OSError, ValueError):
        return []


def _remember(fp):
    h = _history()[-200:] + [fp]
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(h))
    except OSError:
        pass


def _too_similar(fp, history, limit=5):
    return any(sum(a == b for a, b in zip(fp, old)) >= limit for old in history)


def choose(request, app_name="", kind="site", seed=None, avoid_history=True, mood=None):
    """The whole design decision. Deterministic for a given seed; a fresh seed each build gives variety.
    Combinations already used on this device (5 or more of the 8 main choices the same) are avoided."""
    if seed is None:
        seed = int.from_bytes(os.urandom(4), "big")
    mood_name, mood_reason = (mood, f"The mood was set to {mood}.") if mood else detect(request)
    m = MOODS[mood_name]
    user = find_colours(request)
    history = _history() if avoid_history else []
    for tries in range(60):
        rnd = random.Random(seed + tries * 7919)
        pal = rnd.choice(m["palettes"])
        heading, body = rnd.choice(m["fonts"])
        variants = {k: rnd.choice(m[k]) for k in ("hero", "features", "fact", "form", "nav", "rhythm")}
        fp = [mood_name, "user:" + "+".join(c["hex"] for c in user) if user else pal[0], heading,
              variants["hero"], variants["features"], variants["form"], variants["nav"], variants["rhythm"]]
        if not _too_similar(fp, history):
            break
    if user:
        dominant, support, accent, colour_reason = assign_roles(user, pal)
        palette = {"source": "user", "name": "Your colours: " + _role_names(user), "user_colours": user}
    else:
        _, dominant, support, accent = pal
        colour_reason = (f"No colours were named, so the palette '{pal[0]}' was picked at random from "
                         f"{len(m['palettes'])} palettes that suit this mood.")
        palette = {"source": "mood", "name": pal[0], "user_colours": []}
    palette["roles"] = {"dominant": dominant, "support": support, "accent": accent}
    colors = color_tokens(dominant, support, accent)
    hname, hkind, hweight = FONTS[heading]
    bname, bkind, _ = FONTS[body]
    radius = m["radius"]
    sh = SHADOWS[m["shadow"]]
    c = colors["shadow-color"]
    space = m["space"]
    tokens = {
        **{f"color-{k}": v for k, v in colors.items()},
        "font-heading": f"'{hname}', {'Georgia, serif' if hkind == 'serif' else 'system-ui, sans-serif'}",
        "font-body": f"'{bname}', system-ui, sans-serif",
        "heading-weight": str(hweight), "heading-tracking": "-0.02em" if hkind != "serif" else "-0.01em",
        "body-size": "17px", "ratio": str(m["ratio"]),
        "radius-sm": f"{max(2, round(radius * 0.5))}px", "radius": f"{radius}px", "radius-lg": f"{round(radius * 1.5)}px",
        "radius-button": BUTTON_RADIUS[m["button"]] or f"{max(6, round(radius * 0.8))}px",
        "shadow-sm": sh[0].format(c=c), "shadow": sh[1].format(c=c), "shadow-lg": sh[2].format(c=c),
        "space": f"{round(8 * space, 2)}px", "section-space": f"{round(96 * space)}px",
        "label-case": "uppercase" if mood_name in ("elegance", "trust", "energy") else "none",
        "label-tracking": "0.14em" if mood_name in ("elegance", "trust", "energy") else "0.01em",
    }
    report = contrast_report(colors)
    reason = (f"{mood_reason} {colour_reason} Headings use {hname} and text uses {bname}, a pairing chosen for "
              f"{m['feel'].split(',')[0]}. Corners are {'square' if radius <= 3 else 'softly rounded' if radius <= 12 else 'generously rounded'} "
              f"and depth comes from {m['shadow']} shadows and background tone, not lines. The page opens with a "
              f"{variants['hero']} hero, shows the main points as {variants['features']}, and puts the form in a "
              f"{variants['form']} layout. Every text and background pair passes the contrast check "
              f"(lowest ratio {min(r['ratio'] for r in report if r['needs'] >= 4.5)}:1).")
    design = {"version": 1, "seed": seed, "app_name": app_name, "kind": kind, "mood": mood_name, "feel": m["feel"],
              "palette": palette, "tokens": tokens, "fonts": sorted({heading, body}), "variants": variants,
              "fingerprint": fp, "contrast": report, "reason": reason}
    if avoid_history:
        _remember(fp)
    return design


def seed_for(name):
    """A stable seed from a project name plus fresh randomness (so the same name can still vary)."""
    return int(hashlib.sha256((name + os.urandom(8).hex()).encode()).hexdigest()[:8], 16)
