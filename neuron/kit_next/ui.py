"""kit.ui - the design system. Every function returns HTML; text you pass in is escaped (and cleaned
of em dashes) for you. You choose WHAT to show; the theme decides HOW it looks: hero layout, how a
list of items is shown, how a single fact or a form is laid out, colours, fonts, spacing.

Layout     page(title, *parts)   (normally app.page(req, title, *parts))
           hero(title, subtitle, button_text, button_href)
           section(title, *parts, id="")   grid(card, ...)   card(title, *parts)   footer(text)
Text       text(words)   heading(words)   badge(words, kind)   alert(words, kind)   button(words, href)
Numbers    stats(stat(label, value, hint), ...)
Data       table(headers, rows)        rows = list of lists
Forms      form(action, *fields, submit="Save")   field(label, name, type="text")   select(label, name, options)
           textarea(label, name)   search(action, value)
"""
import datetime
import re
from html import escape as _escape

from . import copy as _copy
from . import icons as _icons
from . import theme as _theme


def _esc(value):
    return _escape(_copy.clean("" if value is None else str(value)))


class HTML(str):
    """Ready-made HTML (not escaped again). Components also carry what they contain, so a section can
    lay out its items in the theme's style instead of the order they were written in."""
    kind, meta = "html", None

    def __new__(cls, _html, kind="html", **meta):
        obj = str.__new__(cls, _html)
        obj.kind, obj.meta = kind, meta
        return obj


def esc(value):
    return value if isinstance(value, HTML) else HTML(_esc(value))


def _join(parts):
    return HTML("".join(esc(p) for p in parts if p not in (None, "")))


def raw(html):
    return HTML(html)


def _variants():
    return _theme.load().get("variants", {})


def _icon(title, text="", n=None, quiet=False):
    name = _icons.pick(title, text)
    cls = "icon-wrap quiet" if quiet else "icon-wrap"
    if name:
        return f'<span class="{cls}">{_icons.svg(name)}</span>'
    return f'<span class="{cls} num" aria-hidden="true">{n:02d}</span>' if n is not None else ""


# ---- small parts -------------------------------------------------------------------------------
def text(words):
    return HTML(f"<p>{_esc(words)}</p>", "text", words=str(words))


def heading(words):
    return HTML(f"<h3>{_esc(words)}</h3>", "heading", words=str(words))


def badge(words, kind="info"):
    return HTML(f'<span class="badge badge-{_esc(kind)}">{_esc(words)}</span>', "badge")


def alert(words, kind="info"):
    """kind: info, success, warning or error"""
    return HTML(f'<div class="alert alert-{_esc(kind)}" role="alert">{_esc(words)}</div>', "alert", words=str(words), level=kind)


def button(words, href, kind="primary"):
    return HTML(f'<a class="btn btn-{_esc(kind)}" href="{_esc(href)}">{_esc(words)}</a>', "button", words=str(words), href=href)


def card(title, *content):
    texts = [p.meta["words"] for p in content if isinstance(p, HTML) and p.kind == "text"]
    has_form = any(isinstance(p, HTML) and p.kind == "form" for p in content)
    return HTML(f'<div class="card"><h3>{_esc(title)}</h3>{_join(content)}</div>', "card", title=str(title),
                text=" ".join(texts), has_form=has_form, parts=content)


def grid(*items):
    cards = [(i.meta["title"], i.meta["text"]) for i in items if isinstance(i, HTML) and i.kind == "card"]
    return HTML(f'<div class="grid">{_join(items)}</div>', "grid", items=cards)


def stat(label, value, hint=""):
    return HTML(f'<div class="stat"><div class="stat-label">{_esc(label)}</div><div class="stat-value">{_esc(value)}</div>'
                f'<div class="stat-hint">{_esc(hint)}</div></div>', "stat")


def stats(*items):
    return HTML(f'<div class="stats">{_join(items)}</div>', "stats")


def num(value):
    """A number as people read it: 20000 not 20000.0, 1250.50 with two decimals, never 1.2e+06."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "" if value is None else str(value)
    return str(int(v)) if v.is_integer() else f"{v:.2f}"


def table(headers, rows, empty="Nothing here yet."):
    if not rows:
        return HTML(f'<p class="empty">{_esc(empty)}</p>', "table")
    head = "".join(f'<th scope="col">{_esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return HTML(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>', "table")


def field(label, name, type="text", value="", required=False, placeholder=""):
    """type: text, email, number, password, tel or date"""
    extra = ' step="any"' if type == "number" else ""
    auto = {"email": "email", "tel": "tel", "password": "current-password"}.get(type, "")
    auto = f' autocomplete="{auto}"' if auto else (' autocomplete="name"' if name == "name" else "")
    return HTML(f'<label class="field"><span>{_esc(label)}</span><input type="{_esc(type)}" name="{_esc(name)}" '
                f'value="{_esc(value)}" placeholder="{_esc(placeholder)}"{extra}{auto}{" required" if required else ""}></label>', "field")


def textarea(label, name, value="", required=False):
    return HTML(f'<label class="field"><span>{_esc(label)}</span><textarea name="{_esc(name)}" rows="4"'
                f'{" required" if required else ""}>{_esc(value)}</textarea></label>', "field")


def select(label, name, options, value=""):
    opts = "".join(f'<option{" selected" if str(o) == str(value) else ""}>{_esc(o)}</option>' for o in options)
    return HTML(f'<label class="field"><span>{_esc(label)}</span><select name="{_esc(name)}">{opts}</select></label>', "field")


def form(action, *fields, submit="Save", method="post"):
    return HTML(f'<form class="form" action="{_esc(action)}" method="{_esc(method)}">{_join(fields)}'
                f'<button class="btn btn-primary" type="submit">{_esc(submit)}</button></form>', "form", submit=str(submit), action=action)


def search(action, value="", placeholder="Search"):
    return HTML(f'<form class="search" action="{_esc(action)}" method="get" role="search">'
                f'<input type="search" name="q" value="{_esc(value)}" placeholder="{_esc(placeholder)}" aria-label="Search">'
                '<button class="btn" type="submit">Search</button></form>', "search")


def footer(words):
    return HTML(f'<p class="muted">{_esc(words)}</p>', "footer_text", words=str(words))


# ---- hero ----------------------------------------------------------------------------------------
def hero(title, subtitle="", button_text="", button_href="#", image="", image_alt=""):
    """The opening of a page. image: a picture in static/images (its words in image_alt, for people who cannot see it)."""
    h = HTML("", "hero", title=str(title), subtitle=str(subtitle or ""), button_text=str(button_text or ""), button_href=button_href,
             image=str(image or ""), image_alt=str(image_alt or ""))
    return HTML(_render_hero(h.meta, [], [], _variants().get("hero", "split"), ""), "hero", **h.meta)


def _src(path):
    p = str(path or "")
    return p if p.startswith(("/", "http")) else "/" + p


def photo(src, alt=""):
    """One picture from static/images, with words describing it."""
    return HTML(f'<figure class="photo"><img src="{_esc(_src(src))}" alt="{_esc(alt)}" loading="lazy" decoding="async"></figure>',
                "photo", src=str(src), alt=str(alt))


def photos(*items):
    """A row of pictures between sections (two or three ui.photo(...))."""
    return HTML(f'<section class="section photo-band"><div class="wrap"><div class="photos photos-{len(items)}">{_join(items)}</div></div></section>',
                "photos", count=len(items))


def _cta(meta):
    if not meta.get("button_text"):
        return ""
    return (f'<div class="hero-actions"><a class="btn btn-primary btn-lg" href="{_esc(meta["button_href"])}">{_esc(meta["button_text"])}'
            f'{_icons.svg("arrow-right")}</a></div>')


def _render_hero(m, items, facts, variant, brand):
    h1 = f'<h1>{_esc(m["title"])}</h1>'
    lead = f'<p class="lead">{_esc(m["subtitle"])}</p>' if m.get("subtitle") else ""
    cta = _cta(m)
    if m.get("image"):                 # a real picture (or its labelled placeholder) leads the page in every variant
        pic = (f'<figure class="hero-photo"><img src="{_esc(_src(m["image"]))}" alt="{_esc(m.get("image_alt", ""))}" '
               f'fetchpriority="high" decoding="async"></figure>')
        if variant == "banner":
            return (f'<section class="hero hero-banner on-strong"><div class="wrap hero-grid"><div>{h1}{lead}{cta}</div>{pic}</div></section>')
        if variant in ("centered", "editorial"):
            return (f'<section class="hero hero-{variant} hero-has-photo"><div class="wrap">{h1}{lead}{cta}{pic}</div></section>')
        if variant == "card":
            return (f'<section class="hero hero-card"><div class="wrap hc-grid"><div class="hc-card">{h1}{lead}{cta}</div>{pic}</div></section>')
        return f'<section class="hero hero-split"><div class="wrap hero-grid"><div>{h1}{lead}{cta}</div>{pic}</div></section>'
    # a hero preview shows one kind of thing and at least two of them, and never the items the features section
    # below shows anyway (the design proof found every hero repeating them): only short facts qualify
    peek = facts[:4] if len(facts) >= 2 else []
    if variant == "centered":
        chips = "".join(f'<span class="chip">{_icon(t, x, i + 1)}{_esc(t)}</span>' for i, (t, x) in enumerate(peek))
        return (f'<section class="hero hero-centered"><div class="wrap">{h1}{lead}{cta}'
                f'{f"<div class=chips>{chips}</div>" if chips else ""}</div></section>')
    if variant == "editorial":
        hl = "".join(f'<div class="highlight">{_icon(t, x, i + 1, quiet=True)}<div><strong>{_esc(t)}</strong><span>{_esc(x)}</span></div></div>'
                     for i, (t, x) in enumerate(peek[:3]))
        return (f'<section class="hero hero-editorial"><div class="wrap"><div class="ed-grid">{h1}<div>{lead}{cta}</div></div>'
                f'{f"<div class=highlights>{hl}</div>" if hl else ""}</div></section>')
    if variant == "banner":
        bl = "".join(f'<div class="bl-item">{_icons.svg(_icons.pick(t, x) or "check")}<div><strong>{_esc(t)}</strong>'
                     f'{f"<span>{_esc(x)}</span>" if x else ""}</div></div>' for t, x in peek[:4])
        return (f'<section class="hero hero-banner on-strong"><div class="wrap hero-grid"><div>{h1}{lead}{cta}</div>'
                f'{f"<div class=banner-list>{bl}</div>" if bl else ""}</div></section>')
    if variant == "card":
        sl = "".join(f'<div class="sl-item">{_icon(t, x, i + 1)}{_esc(t)}</div>' for i, (t, x) in enumerate(peek[:4]))
        return (f'<section class="hero hero-card"><div class="wrap hc-grid"><div class="hc-card">{h1}{lead}{cta}</div>'
                f'{f"<div class=side-list>{sl}</div>" if sl else ""}</div></section>')
    # split
    if peek:
        rows = "".join(f'<div class="hv-item">{_icon(t, x, i + 1)}<div><strong>{_esc(t)}</strong>{f"<span>{_esc(x)}</span>" if x else ""}</div></div>'
                       for i, (t, x) in enumerate(peek))
        visual = f'<div class="hero-visual">{rows}</div>'
    else:
        visual = f'<div class="monogram" aria-hidden="true">{_esc((brand or m["title"])[:1].upper())}</div>'
    return f'<section class="hero hero-split"><div class="wrap hero-grid"><div>{h1}{lead}{cta}</div>{visual}</div></section>'


# ---- sections ------------------------------------------------------------------------------------
def section(title, *content, id=""):
    """A part of a page. Show a grid of cards, a short text, or a form: the theme lays each out."""
    v = _variants()
    sid = f' id="{_esc(id)}"' if id else ""
    grids = [p for p in content if isinstance(p, HTML) and p.kind == "grid"]
    forms = [p for p in content if isinstance(p, HTML) and p.kind == "form"]
    texts = [p for p in content if isinstance(p, HTML) and p.kind == "text"]
    others = [p for p in content if not (isinstance(p, HTML) and p.kind in ("grid", "form", "text"))]
    if grids and not forms:
        items = [it for g in grids for it in g.meta["items"]]
        intro = "".join(f'<p class="lead">{_esc(t.meta["words"])}</p>' for t in texts)
        body = _features(items, v.get("features", "cards"))
        html = (f'<section class="section"{sid} data-tone="auto"><div class="wrap"><div class="section-head">'
                f'<h2>{_esc(title)}</h2>{intro}</div>{body}{_join(others)}</div></section>')
        return HTML(html, "section", role="features", title=str(title), items=items)
    if forms:
        f = forms[0]
        intro = "".join(f'<p class="lead">{_esc(t.meta["words"])}</p>' for t in texts)
        variant = v.get("form", "split")
        needs_side = not intro and variant != "panel"
        if variant == "panel":
            inner = f'<div class="form-card"><h2>{_esc(title)}</h2>{intro}{f}</div>'
        else:
            inner = (f'<div class="{"fs-grid" if variant == "split" else "fb-grid"}"><div><h2>{_esc(title)}</h2>{intro}</div>'
                     f'<div class="form-card">{f}</div></div>')
        tone = ' data-tone="strong"' if variant == "band" else ' data-tone="auto"'
        cls = "on-strong " if variant == "band" else ""
        return HTML(f'<section class="section {cls}form-{variant}"{sid}{tone}><div class="wrap">{inner}{_join(others)}</div></section>',
                    "section", role="form", title=str(title), submit=f.meta["submit"], id=id, needs_side=needs_side,
                    form=str(f), others=str(_join(others)), sid=sid)
    if texts and not others:
        words = " ".join(t.meta["words"] for t in texts)
        variant = v.get("fact", "callout")
        if variant == "inline":
            inner = f'<div class="fi-grid"><h2>{_esc(title)}</h2><p class="fact-text">{_esc(words)}</p></div>'
        elif variant == "panel":
            inner = f'<div class="fp-card">{_icon(title, words, 1)}<div><h2>{_esc(title)}</h2><p class="fact-text">{_esc(words)}</p></div></div>'
        else:
            inner = f'{_icon(title, words)}<p class="eyebrow">{_esc(title)}</p><h2 class="fact-text">{_esc(words)}</h2>'
        return HTML(f'<section class="section fact-{variant}"{sid} data-tone="auto" data-fact="1"><div class="wrap">{inner}</div></section>',
                    "section", role="fact", title=str(title), words=words)
    return HTML(f'<section class="section"{sid} data-tone="auto"><div class="wrap"><div class="section-head"><h2>{_esc(title)}</h2></div>'
                f'{_join(content)}</div></section>', "section", role="other", title=str(title))


def _form_side(sec, facts):
    """A side-by-side form with nothing beside it looks empty. Put the page's key facts (hours, price,
    place) next to it; with no facts, centre the form in a panel instead."""
    m = sec.meta
    title = f'<h2>{_esc(m["title"])}</h2>'
    if facts:
        rows = "".join(f'<div class="cf-item">{_icon(t, x, i + 1)}<div><strong>{_esc(t)}</strong><span>{_esc(x)}</span></div></div>'
                       for i, (t, x) in enumerate(facts[:3]))
        band = "strong" in str(sec)[:200]
        grid = "fb-grid" if band else "fs-grid"
        inner = f'<div class="{grid}"><div>{title}<div class="contact-facts">{rows}</div></div><div class="form-card">{m["form"]}</div></div>'
        cls = "section on-strong form-band" if band else "section form-split"
        tone = ' data-tone="strong"' if band else ' data-tone="auto"'
    else:
        inner = f'<div class="form-card">{title}{m["form"]}</div>'
        cls, tone = "section form-panel", ' data-tone="auto"'
    return HTML(f'<section class="{cls}"{m["sid"]}{tone}><div class="wrap">{inner}{m["others"]}</div></section>', "section", **m)


def _features(items, variant):
    if variant == "list":
        body = "".join(f'<div class="fl-item">{_icon(t, x, i + 1)}<div><h3>{_esc(t)}</h3><p>{_esc(x)}</p></div></div>'
                       for i, (t, x) in enumerate(items))
        return f'<div class="f-list">{body}</div>'
    if variant == "rows":
        body = "".join(f'<div class="fr-item"><span class="fr-num">{i + 1:02d}</span><h3>{_esc(t)}</h3><p>{_esc(x)}</p></div>'
                       for i, (t, x) in enumerate(items))
        return f'<div class="f-rows">{body}</div>'
    if variant == "tiles":
        body = "".join(f'<div class="f-tile">{_icon(t, x, i + 1)}<h3>{_esc(t)}</h3><p>{_esc(x)}</p></div>' for i, (t, x) in enumerate(items))
        return f'<div class="f-tiles">{body}</div>'
    if variant == "steps":
        body = "".join(f'<div class="fs-item"><span class="step-num">{i + 1}</span><h3>{_esc(t)}</h3><p>{_esc(x)}</p></div>'
                       for i, (t, x) in enumerate(items))
        return f'<div class="f-steps">{body}</div>'
    body = "".join(f'<div class="f-card">{_icon(t, x, i + 1)}<h3>{_esc(t)}</h3><p>{_esc(x)}</p></div>' for i, (t, x) in enumerate(items))
    return f'<div class="f-cards">{body}</div>'


# ---- the page --------------------------------------------------------------------------------------
NAV_TOGGLE = ('<input type="checkbox" id="nav-toggle" hidden><label for="nav-toggle" class="nav-toggle" aria-label="Menu">'
              '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg></label>')


def _topbar(brand, nav, user, active, variant):
    if len(nav) == 1 and nav[0][1] == "/":
        nav = ()          # a lone "Home" link on a one-page site is noise
    links = "".join(f'<a href="{_esc(href)}"{" class=\"active\" aria-current=\"page\"" if href == active else ""}>{_esc(label)}</a>'
                    for label, href in nav)
    who = f'<span class="who">{_esc(user)}</span><a class="btn btn-ghost" href="/logout">Log out</a>' if user else ""
    toggle = NAV_TOGGLE if links else ""
    mark = f'<span class="brand-mark" aria-hidden="true">{_esc((brand or "N")[:1].upper())}</span>'
    return (f'<header class="topbar nav-{variant}"><div class="topbar-inner"><div class="wrap"><div class="bar">'
            f'<a class="brand" href="/">{mark}{_esc(brand)}</a>{toggle}<nav class="menu" aria-label="Main">{links}</nav>'
            f'<div class="account">{who}</div></div></div></div></header>')


def _footer(brand, nav, extra=""):
    if len(nav) == 1 and nav[0][1] == "/":
        nav = ()
    links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for l, h in nav)
    year = datetime.date.today().year
    return (f'<footer class="footer"><div class="wrap ft-grid"><a class="brand" href="/">{_esc(brand)}</a>'
            f'{f"<nav aria-label=Footer>{links}</nav>" if links else ""}{extra}<p class="copy">&copy; {year} {_esc(brand)}</p></div></footer>')


def _tones(html, rhythm, first_tone):
    """Give sections their background in page order: alternate, flow (one tone) or bands (facts on the strong colour)."""
    order = ["tone-2", "tone-1"] if first_tone == "tone-1" else ["tone-1", "tone-2"]
    state = {"i": 0, "prev": first_tone}

    def repl(m):
        tag = m.group(0)
        if 'data-tone="strong"' in tag:
            tone = "tone-strong"
        elif rhythm == "flow":
            tone = "tone-1"
        elif rhythm == "bands" and 'data-fact="1"' in tag and state["prev"] != "tone-strong":
            tone = "tone-strong"
        else:
            tone = order[state["i"] % 2]
            state["i"] += 1
        if tone == "tone-strong" and state["prev"] == "tone-strong":
            tone = "tone-1"
        state["prev"] = tone
        tag = tag.replace('class="section', f'class="section {tone}{" on-strong" if tone == "tone-strong" else ""}', 1)
        return tag
    return re.sub(r'<section class="section[^>]*>', repl, html)


def page(title, *content, brand="", nav=(), user=None, active="", narrow=False):
    th = _theme.load()
    v = th.get("variants", {})
    brand = brand or th.get("app_name") or title
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_esc(title)}{" | " + _esc(brand) if brand and brand != title else ""}</title>'
            '<link rel="stylesheet" href="/static/theme.css"></head><body>'
            '<a class="skip" href="#main">Skip to content</a>')
    top = _topbar(brand, nav, user, active, v.get("nav", "bar"))
    heroes = [p for p in content if isinstance(p, HTML) and p.kind == "hero"]
    if narrow:
        parts = list(content)
        inner = []
        for p in parts:
            if isinstance(p, HTML) and p.kind == "card":
                inner.append(f'<div class="card"><h1>{_esc(p.meta["title"])}</h1>{_join(p.meta["parts"])}</div>')
            else:
                inner.append(esc(p))
        body = f'<main id="main" class="wrap login-wrap">{"".join(inner)}</main>'
        return HTML(head + top + body + _footer(brand, ()) + "</body></html>")
    if heroes:
        sections = [p for p in content if isinstance(p, HTML) and p.kind == "section"]
        items = next((s.meta["items"] for s in sections if s.meta.get("role") == "features"), [])
        facts = [(s.meta["title"], s.meta["words"]) for s in sections if s.meta.get("role") == "fact"]
        form_sec = next((s for s in sections if s.meta.get("role") == "form"), None)
        h = dict(heroes[0].meta)
        if form_sec is not None and form_sec.meta.get("id"):
            # one clear main action: the hero button leads to the form and says what it is for
            # ("Ask for a call back"), not the form's own short submit word ("Send")
            weak = not h.get("button_text") or h["button_text"].strip().lower() == form_sec.meta["submit"].strip().lower() \
                or len(h["button_text"].split()) == 1
            if weak and len(form_sec.meta["title"].split()) <= 5:
                h["button_text"], h["button_href"] = form_sec.meta["title"], "#" + form_sec.meta["id"]
            elif not h.get("button_text"):
                h["button_text"], h["button_href"] = form_sec.meta["submit"], "#" + form_sec.meta["id"]
        variant = v.get("hero", "split")
        rendered = []
        # facts shown beside the form are MOVED there, never shown twice on the page
        moved = set(facts[:3]) if form_sec is not None and form_sec.meta.get("needs_side") else set()
        for p in content:
            if isinstance(p, HTML) and p.kind == "section" and p.meta.get("role") == "fact" and (p.meta["title"], p.meta["words"]) in moved:
                continue
            if isinstance(p, HTML) and p.kind == "section" and p.meta.get("role") == "form" and p.meta.get("needs_side"):
                p = _form_side(p, facts)
            if p is heroes[0]:
                rendered.append(_render_hero(h, items, facts, variant, brand))
            elif isinstance(p, HTML) and p.kind == "photos":         # already a full-width band of its own
                rendered.append(esc(p))
            elif isinstance(p, HTML) and p.kind == "section":
                rendered.append(str(p))
            else:
                rendered.append(f'<section class="section" data-tone="auto"><div class="wrap">{esc(p)}</div></section>')
        first = "tone-strong" if variant == "banner" else "tone-2" if variant == "card" else "tone-1"
        body = f'<main id="main">{_tones("".join(rendered), v.get("rhythm", "alternate"), first)}</main>'
        return HTML(head + top + body + _footer(brand, nav) + "</body></html>")
    # an app page: title, then content; a card holding a form sits beside the rest on wide screens
    side = [p for p in content if isinstance(p, HTML) and p.kind == "card" and p.meta.get("has_form")]
    rest = [p for p in content if p not in side]
    only_alert = rest and all(isinstance(p, HTML) and p.kind in ("alert", "button") for p in rest) and not side
    if only_alert:
        body = f'<main id="main" class="wrap app-main thanks"><h1>{_esc(title)}</h1>{_join(rest)}</main>'
    elif side and rest:
        body = (f'<main id="main" class="wrap app-main"><div class="page-head"><h1>{_esc(title)}</h1></div>'
                f'<div class="app-grid"><div class="app-primary">{_join(rest)}</div><aside class="app-side">{_join(side)}</aside></div></main>')
    else:
        body = f'<main id="main" class="wrap app-main"><div class="page-head"><h1>{_esc(title)}</h1></div>{_join(content)}</main>'
    return HTML(head + top + body + _footer(brand, nav) + "</body></html>")
