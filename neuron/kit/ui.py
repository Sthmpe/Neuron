"""kit.ui - the design system. Every function returns HTML; text you pass in is escaped for you.
Build a page by nesting these components; never write raw <html> or CSS.

Layout     page(title, *content)                      (normally call app.page(req, title, *content))
           hero(title, subtitle, button_text, button_href)
           section(title, *content)   grid(*cards)   card(title, *content)   footer(text)
Text       text(words)   heading(words)   badge(words, kind)   alert(words, kind)   button(words, href)
Numbers    stats(stat(label, value, hint), ...)
Data       table(headers, rows)        rows = list of lists
Forms      form(action, *fields, submit="Save")   field(label, name, type="text")   select(label, name, options)
           textarea(label, name)   search(action, value)
"""
from html import escape as _escape


def _esc(value):
    return _escape("" if value is None else str(value))


class HTML(str):
    """Marks a string as ready-made HTML so it is not escaped again."""


def esc(value):
    return value if isinstance(value, HTML) else HTML(_esc("" if value is None else str(value)))


def _join(parts):
    return HTML("".join(esc(p) for p in parts if p not in (None, "")))


def raw(html):
    return HTML(html)


def page(title, *content, brand="", nav=(), user=None, active="", narrow=False):
    links = "".join(f'<a href="{_esc(href)}"{" class=\"active\"" if href == active else ""}>{_esc(label)}</a>'
                    for label, href in nav)
    who = (f'<span class="who">{_esc(user)}</span><a class="btn btn-ghost" href="/logout">Log out</a>' if user else "")
    toggle = '<input type="checkbox" id="nav-toggle" hidden><label for="nav-toggle" class="nav-toggle" aria-label="Menu">&#9776;</label>' if links else ""
    return HTML(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{_esc(title)}{" - " + _esc(brand) if brand else ""}</title>'
        '<link rel="stylesheet" href="/static/neuron.css"></head><body>'
        f'<header class="topbar"><div class="wrap bar"><a class="brand" href="/">{_esc(brand or title)}</a>'
        f'{toggle}<nav class="menu">{links}</nav><div class="account">{who}</div></div></header>'
        f'<main class="wrap{" narrow" if narrow else ""}"><h1 class="page-title">{_esc(title)}</h1>{_join(content)}</main>'
        '</body></html>')


def hero(title, subtitle="", button_text="", button_href="#"):
    btn = f'<a class="btn btn-primary btn-lg" href="{_esc(button_href)}">{_esc(button_text)}</a>' if button_text else ""
    return HTML(f'<section class="hero"><h2>{_esc(title)}</h2><p>{_esc(subtitle)}</p>{btn}</section>')


def section(title, *content, id=""):
    return HTML(f'<section class="section"{f" id=\"{_esc(id)}\"" if id else ""}><h2>{_esc(title)}</h2>{_join(content)}</section>')


def grid(*items):
    return HTML(f'<div class="grid">{_join(items)}</div>')


def card(title, *content):
    return HTML(f'<div class="card"><h3>{_esc(title)}</h3>{_join(content)}</div>')


def heading(words):
    return HTML(f"<h3>{_esc(words)}</h3>")


def text(words):
    return HTML(f"<p>{_esc(words)}</p>")


def badge(words, kind="info"):
    return HTML(f'<span class="badge badge-{_esc(kind)}">{_esc(words)}</span>')


def alert(words, kind="info"):
    """kind: info, success, warning or error"""
    return HTML(f'<div class="alert alert-{_esc(kind)}" role="alert">{_esc(words)}</div>')


def button(words, href, kind="primary"):
    return HTML(f'<a class="btn btn-{_esc(kind)}" href="{_esc(href)}">{_esc(words)}</a>')


def stat(label, value, hint=""):
    return HTML(f'<div class="stat"><div class="stat-label">{_esc(label)}</div>'
                f'<div class="stat-value">{_esc(value)}</div><div class="stat-hint">{_esc(hint)}</div></div>')


def stats(*items):
    return HTML(f'<div class="stats">{_join(items)}</div>')


def num(value):
    """A number as people read it: 20000 not 20000.0, 1250.50 with two decimals, never 1.2e+06."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "" if value is None else str(value)
    return str(int(v)) if v.is_integer() else f"{v:.2f}"


def table(headers, rows, empty="Nothing here yet."):
    if not rows:
        return HTML(f'<p class="empty">{_esc(empty)}</p>')
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return HTML(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def field(label, name, type="text", value="", required=False, placeholder=""):
    """type: text, email, number, password, tel or date"""
    extra = ' step="any"' if type == "number" else ""
    return HTML(f'<label class="field"><span>{_esc(label)}</span><input type="{_esc(type)}" name="{_esc(name)}" '
                f'value="{_esc(value)}" placeholder="{_esc(placeholder)}"{extra}{" required" if required else ""}></label>')


def textarea(label, name, value="", required=False):
    return HTML(f'<label class="field"><span>{_esc(label)}</span><textarea name="{_esc(name)}" rows="4"'
                f'{" required" if required else ""}>{_esc(value)}</textarea></label>')


def select(label, name, options, value=""):
    opts = "".join(f'<option{" selected" if str(o) == str(value) else ""}>{_esc(o)}</option>' for o in options)
    return HTML(f'<label class="field"><span>{_esc(label)}</span><select name="{_esc(name)}">{opts}</select></label>')


def form(action, *fields, submit="Save", method="post"):
    return HTML(f'<form class="form" action="{_esc(action)}" method="{_esc(method)}">{_join(fields)}'
                f'<button class="btn btn-primary" type="submit">{_esc(submit)}</button></form>')


def search(action, value="", placeholder="Search"):
    return HTML(f'<form class="search" action="{_esc(action)}" method="get" role="search">'
                f'<input type="search" name="q" value="{_esc(value)}" placeholder="{_esc(placeholder)}" aria-label="Search">'
                '<button class="btn" type="submit">Search</button></form>')


def footer(words):
    return HTML(f'<footer class="footer">{_esc(words)}</footer>')
