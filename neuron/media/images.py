"""Pictures for what NEURON makes: the owner's photos first, licensed photos when online, never invented ones.

A project lists the pictures it needs in images.json (the manifest), one slot per picture:
  {"slot": "hero", "purpose": "fresh bread on the counter", "query": "bread bakery counter", "shape": "wide",
   "file": "static/images/hero.svg", "status": "needed" | "owner" | "licensed", "source": {...}}

For every slot, in this order:
  1. the owner's own photos (attached to the job, or already in the project's photos folder): matched to a slot by the
     words in the file name, otherwise in order. status "owner".
  2. offline, nothing else available: a placeholder drawn from the project's own colours and clearly labelled
     "Image needed", status "needed". The job says "images needed" and waits for the internet for this step only.
  3. online: a photo from Wikimedia Commons whose licence allows use on a business website (public domain, CC0,
     CC BY, CC BY-SA), downloaded at a fitting size. Title, author, licence, licence link and page link are recorded in
     the manifest and in IMAGE_CREDITS.md, so attribution is never lost. status "licensed".
Pages refer to a slot's file; when a placeholder is replaced, references to the old file name are updated.
"""
import html
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SHAPES = {"wide": (1600, 900), "tall": (900, 1200), "square": (1000, 1000), "banner": (1800, 600)}
# Licences that allow use on a business website with attribution at most. Non-commercial and no-derivatives are refused.
LICENCE_OK = re.compile(r"^(public domain|pd\b|pdm|cc0|cc[- ]by(-sa)?[- ]\d|cc[- ]by(-sa)?$)", re.I)
LICENCE_BAD = re.compile(r"\bnc\b|\bnd\b|non-?commercial|fair use|no derivatives", re.I)
AVOID_TITLE = re.compile(r"\b(logo|map|diagram|chart|coat of arms|flag|seal|icon|drawing|illustration|poster|scan|"
                         r"document|svg|screenshot|sign|stamp|banknote|postcard|painting|engraving|lithograph|etching)\b", re.I)
USER_AGENT = "NEURON-local-assistant/0.1 (offline-first desktop assistant; image search for the owner's project)"


class RateLimited(Exception):
    """The photo site asked NEURON to slow down. NEURON stops asking and the step tries again later by itself."""

    def __init__(self, msg, retry_after=600):
        super().__init__(msg)
        self.retry_after = retry_after


# ---- manifest ---------------------------------------------------------------------------------------------------
class Manifest:
    def __init__(self, project, image_dir="static/images"):
        self.project = Path(project)
        self.path = self.project / "images.json"
        self.image_dir = image_dir
        try:
            self.slots = json.loads(self.path.read_text())["slots"]
        except (OSError, ValueError, KeyError):
            self.slots = []

    def add(self, slot, purpose, query=None, shape="wide"):
        if not any(s["slot"] == slot for s in self.slots):
            self.slots.append({"slot": slot, "purpose": purpose, "query": query or purpose, "shape": shape,
                               "file": "", "status": "needed", "source": None})
        return self

    def get(self, slot):
        return next(s for s in self.slots if s["slot"] == slot)

    def needed(self):
        return [s for s in self.slots if s["status"] == "needed"]

    def save(self):
        self.project.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"slots": self.slots}, indent=1))
        write_credits(self)

    def summary(self):
        by = {}
        for s in self.slots:
            by[s["status"]] = by.get(s["status"], 0) + 1
        return by


def write_credits(m):
    """IMAGE_CREDITS.md: where every picture came from. Written whenever the manifest is saved."""
    lines = ["# Image credits", ""]
    for s in m.slots:
        src = s.get("source") or {}
        if s["status"] == "licensed":
            lines.append(f"- {s['slot']}: \"{src.get('title', '')}\" by {src.get('author') or 'unknown author'}, "
                         f"{src.get('licence', '')} ({src.get('licence_url', '')}), from {src.get('page', '')}, fetched {src.get('fetched', '')}")
        elif s["status"] == "owner":
            lines.append(f"- {s['slot']}: the owner's own photo ({src.get('original', '')})")
        else:
            lines.append(f"- {s['slot']}: IMAGE NEEDED ({s['purpose']}); a labelled placeholder is shown until a photo is added")
    (m.project / "IMAGE_CREDITS.md").write_text("\n".join(lines) + "\n")


# ---- 1. the owner's photos ----------------------------------------------------------------------------------------
def _words(text):
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def use_owner_photos(m, photos):
    """Give each slot one of the owner's photos: best word match between file name and slot first, then in order."""
    photos = [Path(p) for p in photos if Path(p).suffix.lower() in PHOTO_EXT]
    free = list(photos)
    slots = [s for s in m.slots if s["status"] != "owner"]
    for s in sorted(slots, key=lambda s: -max([len(_words(p.stem) & _words(s["slot"] + " " + s["purpose"])) for p in free] or [0])):
        if not free:
            break
        best = max(free, key=lambda p: len(_words(p.stem) & _words(s["slot"] + " " + s["purpose"])))
        free.remove(best)
        _place(m, s, best, {"original": best.name}, "owner")
    return m


def _place(m, s, src_file, source, status):
    dest_rel = f"{m.image_dir}/{s['slot']}{Path(src_file).suffix.lower()}"
    dest = m.project / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(src_file).resolve() != dest.resolve():
        shutil.copy(src_file, dest)
    old = s.get("file")
    s.update(file=dest_rel, status=status, source=source)
    if old and old != dest_rel:
        relink(m.project, old, dest_rel)
        if (m.project / old).exists() and old.endswith(".svg"):
            (m.project / old).unlink()


def relink(project, old, new):
    """Point every page, style sheet and script in the project from the old file to the new one."""
    for f in Path(project).rglob("*"):
        if f.is_file() and f.suffix in (".html", ".css", ".js", ".py", ".md", ".json") and ".neuron" not in f.parts:
            t = f.read_text(errors="replace")
            if old in t:
                f.write_text(t.replace(old, new))


# ---- 2. placeholders drawn from the project's colours -------------------------------------------------------------
def _mix(hex1, hex2, t):
    a = [int(hex1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def placeholder_svg(purpose, palette, shape="wide"):
    """A calm, on-brand placeholder that says plainly that a photo is still needed. palette = (dominant, support, accent)."""
    dominant, support, accent = palette
    w, h = SHAPES.get(shape, SHAPES["wide"])
    light, deep = _mix(dominant, "#ffffff", 0.55), _mix(support, dominant, 0.25)
    label = html.escape(purpose[:70])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="Image needed: {label}">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{deep}"/></linearGradient>
<pattern id="p" width="48" height="48" patternUnits="userSpaceOnUse"><circle cx="24" cy="24" r="1.6" fill="#ffffff" opacity=".22"/></pattern></defs>
<rect width="{w}" height="{h}" fill="url(#g)"/><rect width="{w}" height="{h}" fill="url(#p)"/>
<circle cx="{w * 0.82:.0f}" cy="{h * 0.2:.0f}" r="{min(w, h) * 0.32:.0f}" fill="{accent}" opacity=".18"/>
<g font-family="system-ui, -apple-system, Segoe UI, sans-serif" fill="#ffffff" text-anchor="middle">
<text x="{w / 2:.0f}" y="{h / 2 - 8:.0f}" font-size="{max(28, w // 30)}" font-weight="600" letter-spacing="1">Image needed</text>
<text x="{w / 2:.0f}" y="{h / 2 + max(28, w // 30) + 4:.0f}" font-size="{max(18, w // 55)}" opacity=".9">{label}</text></g></svg>
'''


def fill_placeholders(m, palette):
    """Every slot without a photo gets a labelled placeholder in the project's colours (status stays 'needed')."""
    for s in m.slots:
        if s["status"] == "needed" and not (s.get("file") and (m.project / s["file"]).exists()):
            rel = f"{m.image_dir}/{s['slot']}.svg"
            (m.project / rel).parent.mkdir(parents=True, exist_ok=True)
            (m.project / rel).write_text(placeholder_svg(s["purpose"], palette, s.get("shape", "wide")))
            s["file"] = rel
    return m


# ---- 3. licensed photos from Wikimedia Commons ---------------------------------------------------------------------
def _plain(value):
    return re.sub(r"<[^>]+>", "", html.unescape(str(value or ""))).strip()


class CommonsProvider:
    """Searches Wikimedia Commons for photos with a licence that allows use on a business website."""
    api = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, opener=None, pause=1.0):
        self.opener = opener or urllib.request.build_opener()
        self.pause = pause

    def _get(self, url, binary=False):
        """One polite request. A 'too many requests' answer is never retried in a loop: NEURON stops and comes back later."""
        for attempt in range(3):
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with self.opener.open(req, timeout=60) as r:
                    data = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                try:
                    wait = int(e.headers.get("Retry-After") or 600)
                except ValueError:
                    wait = 600
                if wait <= 10 and attempt < 2:      # "wait a second": do exactly that, then ask once more
                    time.sleep(wait + 1)
                    continue
                raise RateLimited("Wikimedia Commons asked NEURON to slow down", max(wait, 600)) from e
        time.sleep(self.pause)            # a short pause between requests, so one site is never hammered
        return data if binary else json.loads(data)

    def search(self, query, width=1600, limit=12):
        params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6", "gsrlimit": str(limit),
                  "gsrsearch": f"filetype:bitmap {query}", "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime",
                  "iiurlwidth": str(width), "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl|ObjectName"}
        data = self._get(self.api + "?" + urllib.parse.urlencode(params))
        out = []
        for p in sorted((data.get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
            ii = (p.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata") or {}
            out.append({"title": _plain(meta.get("ObjectName", {}).get("value")) or p.get("title", "").replace("File:", ""),
                        "file_title": p.get("title", ""), "mime": ii.get("mime", ""), "width": ii.get("width", 0),
                        "height": ii.get("height", 0), "url": ii.get("url", ""), "thumb": ii.get("thumburl", ""),
                        "bytes": ii.get("size", 0),
                        "page": ii.get("descriptionurl", ""), "author": _plain(meta.get("Artist", {}).get("value"))[:120],
                        "licence": _plain(meta.get("LicenseShortName", {}).get("value")),
                        "licence_url": _plain(meta.get("LicenseUrl", {}).get("value"))})
        return out

    def download(self, cand):
        """The ready-made copy at the size the page needs (thumb.wikimedia.org, what Wikimedia asks clients to use);
        the original file only if there is none or it fails. Shrunk locally either way."""
        urls = [u for u in (cand.get("thumb"),) if u] + ([cand["url"]] if cand.get("bytes", 0) <= 25_000_000 else [])
        last = None
        for url in urls:
            try:
                return self._get(url, binary=True)
            except (RateLimited, urllib.error.URLError, OSError) as e:
                last = e                   # the other copy lives on another server: try it before giving up
        raise last or OSError("no download link")


def shrink(path, width):
    """Resize a downloaded photo to the width the page needs and drop its metadata (Pillow if installed; else as is)."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return path
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        out = path.with_suffix(".jpg")
        im.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
    if out != path:
        path.unlink()
    return out


def acceptable(c, shape="wide"):
    """Why a candidate photo cannot be used ('' if it can)."""
    if c["mime"] not in ("image/jpeg", "image/png", "image/webp"):
        return "not a photo format"
    if LICENCE_BAD.search(c["licence"]) or not LICENCE_OK.search(c["licence"]):
        return f"licence '{c['licence'] or 'unknown'}' does not allow use on a business website"
    if AVOID_TITLE.search(c["title"] + " " + c["file_title"]):
        return "looks like a logo, map, drawing or document, not a photo"
    need_w, need_h = SHAPES.get(shape, SHAPES["wide"])
    if c["width"] < need_w * 0.6:
        return f"too small ({c['width']} px wide)"
    ratio, want = c["width"] / max(1, c["height"]), need_w / need_h
    if (want >= 1) != (ratio >= 1) and abs(ratio - want) > 0.5:
        return "wrong shape for this place on the page"
    return ""


def fetch_licensed(m, provider, effects=None, log=print):
    """Online: replace each placeholder with a suitable licensed photo.
    Returns {"filled": [...], "not_found": [...], "retry_after": seconds or None}. retry_after is set when the photo site
    asked NEURON to slow down: it stops at once (photos found so far are kept) and the step is tried again later."""
    used = {(s.get("source") or {}).get("page") for s in m.slots}
    filled, not_found, retry_after = [], [], None
    for s in m.needed():
        try:
            cands = provider.search(s["query"], width=SHAPES.get(s.get("shape", "wide"), SHAPES["wide"])[0])
        except RateLimited as e:
            retry_after = e.retry_after
            break
        width = SHAPES.get(s.get("shape", "wide"), SHAPES["wide"])[0]
        pick, reasons, tmp = None, [], None
        for c in cands:
            why = acceptable(c, s.get("shape", "wide")) or ("already used on this site" if c["page"] in used else "")
            if why:
                reasons.append(why)
                continue
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[c["mime"]]
            tmp = m.project / ".neuron" / "downloads" / f"{s['slot']}{ext}"
            tmp.parent.mkdir(parents=True, exist_ok=True)

            def download(c=c, tmp=tmp):
                tmp.write_bytes(provider.download(c))
                return {"bytes": tmp.stat().st_size, "page": c["page"]}

            try:
                res = effects.once(f"image:{m.project.name}:{s['slot']}:{c['page']}", f"download the photo '{c['title'][:60]}' for {s['slot']}",
                                   download, repeat_safe=True) if effects else download()
                if not tmp.exists() or tmp.stat().st_size < 1000:      # a replayed record without the file: fetch it again
                    res = download()
            except RateLimited as e:
                retry_after = e.retry_after
                break
            except (urllib.error.URLError, OSError) as e:
                reasons.append(f"download failed ({type(e).__name__})")
                continue                    # one failed download never stops the step: try the next suitable photo
            pick = c
            break
        if retry_after:
            break
        if pick is None:
            not_found.append({"slot": s["slot"], "why": "; ".join(sorted(set(reasons))[:3]) or "no results"})
            continue
        tmp = shrink(tmp, width)
        source = {k: pick[k] for k in ("title", "author", "licence", "licence_url", "page")}
        source.update(provider="Wikimedia Commons", fetched=time.strftime("%Y-%m-%d"), bytes=tmp.stat().st_size)
        _place(m, s, tmp, source, "licensed")
        used.add(pick["page"])
        filled.append(s["slot"])
        log(f"  image {s['slot']}: {pick['title'][:60]} ({pick['licence']})")
    m.save()
    return {"filled": filled, "not_found": not_found, "retry_after": retry_after}


def prepare(project, slots, palette, owner_photos=(), image_dir="static/images"):
    """Offline part, run while building: owner photos first, placeholders for the rest. Returns the manifest."""
    m = Manifest(project, image_dir)
    for s in slots:
        m.add(s["slot"], s["purpose"], s.get("query"), s.get("shape", "wide"))
    use_owner_photos(m, owner_photos)
    fill_placeholders(m, palette)
    m.save()
    return m
