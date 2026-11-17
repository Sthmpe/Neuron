"""Colour maths in OKLCH, a perceptual colour space: equal steps of lightness look equal, and changing
lightness keeps the hue recognisable. Everything else in the design engine builds on these functions."""
import math
import re

HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def parse_hex(text):
    m = HEX.match(text.strip())
    if not m:
        raise ValueError(f"not a hex colour: {text}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklch(rgb):
    r, g, b = (_lin(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    C = math.hypot(a, bb)
    H = math.degrees(math.atan2(bb, a)) % 360
    return (L, C, H)


def _oklch_to_linear(lch):
    L, C, H = lch
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def in_gamut(lch, eps=1e-4):
    return all(-eps <= c <= 1 + eps for c in _oklch_to_linear(lch))


def oklch_to_rgb(lch):
    """Converts, reducing chroma (never hue or lightness) until the colour can be shown on a screen."""
    L, C, H = lch
    L = max(0.0, min(1.0, L))
    if not in_gamut((L, C, H)):
        lo, hi = 0.0, C
        for _ in range(24):
            mid = (lo + hi) / 2
            if in_gamut((L, mid, H)):
                lo = mid
            else:
                hi = mid
        C = lo
    return tuple(_gam(max(0.0, min(1.0, c))) for c in _oklch_to_linear((L, C, H)))


def hex_to_oklch(h):
    return rgb_to_oklch(parse_hex(h))


def oklch_to_hex(lch):
    return to_hex(oklch_to_rgb(lch))


def luminance(h):
    r, g, b = (_lin(c) for c in parse_hex(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio between two hex colours (1 to 21)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hue_distance(h1, h2):
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def with_lightness(h, L):
    _, C, H = hex_to_oklch(h)
    return oklch_to_hex((L, C, H))


def ensure_contrast(fg, bg, target=4.5):
    """Return fg, changed ONLY in lightness (same hue, chroma reduced only if the screen cannot show it),
    so that it reaches `target` contrast against bg. Moves away from the background's lightness."""
    if contrast(fg, bg) >= target:
        return fg
    L, C, H = hex_to_oklch(fg)
    darker = luminance(bg) > 0.18
    lo, hi = (0.0, L) if darker else (L, 1.0)
    best = oklch_to_hex((0.0 if darker else 1.0, C, H))
    for _ in range(30):
        mid = (lo + hi) / 2
        cand = oklch_to_hex((mid, C, H))
        if contrast(cand, bg) >= target:
            best = cand
            if darker:
                lo = mid
            else:
                hi = mid
        else:
            if darker:
                hi = mid
            else:
                lo = mid
    return best


def on_color(bg, dark="#111111", light="#ffffff", target=4.5):
    """Text colour for use on top of bg: whichever of dark/light passes; if neither, the better one."""
    cd, cl = contrast(dark, bg), contrast(light, bg)
    if cl >= target and (cl >= cd or cd < target):
        return light
    if cd >= target:
        return dark
    return light if cl > cd else dark


def button_pair(color, page_bg, dark_ink, target=4.5):
    """A button colour and its text colour, keeping the hue. Designers put white text on mid and dark
    colours and dark text on light ones (yellow, lime, sand), so: for a colour that is not light,
    first try white text, darkening the button a little (at most 0.12 lightness) if needed; for a light
    colour, dark text. Only if neither works is the lightness moved further."""
    L, Cc, H = hex_to_oklch(color)
    if L < 0.72:
        for step in range(0, 25):
            cand = oklch_to_hex((max(0.0, L - step * 0.005), Cc, H)) if step else color
            if contrast("#ffffff", cand) >= target:
                return cand, "#ffffff"
    if contrast(dark_ink, color) >= target:
        return color, dark_ink
    if contrast("#ffffff", color) >= target:
        return color, "#ffffff"
    for step in range(1, 80):
        for direction, text in ((1, dark_ink), (-1, "#ffffff")):
            cand = oklch_to_hex((max(0.0, min(1.0, L + direction * step * 0.005)), Cc, H))
            if contrast(text, cand) >= target:
                return cand, text
    return ensure_contrast(color, "#ffffff", target), "#ffffff"


SCALE_L = {50: 0.975, 100: 0.948, 200: 0.9, 300: 0.83, 400: 0.74, 500: 0.65, 600: 0.56, 700: 0.48, 800: 0.4,
           900: 0.32, 950: 0.25}


def tonal_scale(h):
    """Tints and shades (50 lightest to 950 darkest) that all keep the colour's hue. Chroma follows
    the base colour, tapering near white and black so tints stay soft and shades stay rich.
    The step closest to the base colour is the base colour itself, so the brand stays exact."""
    L0, C0, H = hex_to_oklch(h)
    scale = {}
    for step, L in SCALE_L.items():
        taper = 1 - (abs(L - 0.6) / 0.6) ** 1.6
        C = C0 * max(0.12, min(1.0, taper * 1.15))
        if L > 0.9:
            C = min(C, 0.035 if L > 0.94 else 0.06)
        scale[step] = oklch_to_hex((L, C, H))
    nearest = min(SCALE_L, key=lambda s: abs(SCALE_L[s] - L0))
    scale[nearest] = to_hex(parse_hex(h))
    return scale


def neutral_scale(hue, chroma=0.008):
    """Greys that carry a trace of the main hue, so they match the palette instead of looking dead."""
    return {step: oklch_to_hex((L, chroma if L < 0.97 else chroma * 0.6, hue)) for step, L in
            {0: 1.0, 25: 0.988, 50: 0.975, 100: 0.955, 200: 0.92, 300: 0.86, 400: 0.72, 500: 0.58, 600: 0.48,
             700: 0.39, 800: 0.30, 900: 0.22, 950: 0.17}.items()}
