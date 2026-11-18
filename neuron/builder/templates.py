"""Deterministic file templates: write any build file straight from the spec, with no model.

Used as the last resort in the builder (after the model has failed a task 3 times), so that a build can
finish no matter which model is installed. Every file written this way is recorded in project state and
counted in results, so it is always clear how much of an app the model wrote and how much came from here.
"""
from . import relations
from .spec import INPUT_TYPE, SQL_TYPE


def schema_py(spec):
    lines = ["def setup(app):"]
    for t in spec["entities"] + spec["forms"]:
        cols = ", ".join(f"{f['name']} {SQL_TYPE.get(f['type'], 'TEXT')}" for f in t["fields"])
        lines.append(f'    app.db.execute("CREATE TABLE IF NOT EXISTS {t["name"]}(id INTEGER PRIMARY KEY, {cols})")')
    if spec["kind"] == "app":
        if spec["login_required"]:
            lines += [f'    app.add_user({spec["username"]!r}, {spec["password"]!r})', "    app.enable_login()"]
        nav = ([("Dashboard", "/")] if spec["dashboard"] else []) + [(e["label"], "/" + e["name"]) for e in spec["entities"]]
    else:
        nav = [("Home", "/")]
    lines.append(f"    app.nav = {nav!r}")
    return "\n".join(lines) + "\n"


def _fields(fs):
    return ", ".join(f'ui.field({f["label"]!r}, {f["name"]!r}, type={INPUT_TYPE[f["type"]]!r})' for f in fs)


def entity_py(spec, e):
    login = ", login=True" if spec["login_required"] else ""
    cols = ", ".join(f["name"] for f in e["fields"])
    marks = ", ".join("?" for _ in e["fields"])
    vals = ", ".join(f'req.form.get({f["name"]!r}, "")' for f in e["fields"])
    row = ", ".join([f'r[{f["name"]!r}]' for f in e["fields"]] + [f'ui.num(r[{c["name"]!r}])' for c in e.get("computed", [])])
    heads = [f["label"] for f in e["fields"]] + [c["label"] for c in e.get("computed", [])]
    from .computed import select_sql
    select = select_sql(e)
    before, after = relations.template_post(spec, e)
    fields = ", ".join(relations.ui_field_code(spec, f, INPUT_TYPE.get(f["type"], "text")) for f in e["fields"])
    return f'''from kit.web import redirect
from kit import ui


def register(app):
    @app.route("/{e["name"]}", methods=["GET", "POST"]{login})
    def {e["name"]}(req):
        if req.method == "POST":
{before}            app.db.execute("INSERT INTO {e["name"]}({cols}) VALUES({marks})", [{vals}])
{after}            return redirect("/{e["name"]}")
        q = req.query.get("q", "")
        found = app.db.query("{select} WHERE {e["search_field"]} LIKE ? ORDER BY id DESC", ["%" + q + "%"])
        rows = [[{row}] for r in found]
        return app.page(req, {e["label"]!r}, ui.search("/{e["name"]}", q), ui.table({heads!r}, rows),
                        ui.card("Add", ui.form("/{e["name"]}", {fields}, submit="Add")))
'''


def dashboard_py(spec):
    login = ", login=True" if spec["login_required"] else ""
    stats = []
    for d in spec["dashboard"]:
        if d["kind"] == "sum":
            stats.append(f'ui.stat({d["label"]!r}, ui.num(app.db.value("SELECT COALESCE(SUM({d["sql"]}), 0) FROM {d["entity"]}")))')
            continue
        where = f' WHERE {d["field"]} < {d["below"]:g}' if d["kind"] == "count_below" else ""
        stats.append(f'ui.stat({d["label"]!r}, app.db.value("SELECT COUNT(*) FROM {d["entity"]}{where}"))')
    return f'''from kit import ui


def register(app):
    @app.route("/"{login})
    def dashboard(req):
        return app.page(req, "Dashboard", ui.stats({", ".join(stats)}))
'''


def home_py(spec):
    h = spec["home"]
    parts = [f'ui.hero({h["headline"]!r}, {h["subheadline"]!r})']
    for s in h["sections"]:
        if s["items"]:
            cards = ", ".join(f'ui.card({i["title"]!r}, ui.text({i["text"]!r}))' for i in s["items"])
            parts.append(f'ui.section({s["title"]!r}, ui.grid({cards}))')
        else:
            parts.append(f'ui.section({s["title"]!r}, ui.text({s["text"]!r}))')
    routes = ""
    for f in spec["forms"]:
        parts.append(f'ui.section({f["title"]!r}, ui.form("/{f["name"]}", {_fields(f["fields"])}, submit={f["button"]!r}), id={f["name"]!r})')
        cols = ", ".join(x["name"] for x in f["fields"])
        marks = ", ".join("?" for _ in f["fields"])
        vals = ", ".join(f'req.form.get({x["name"]!r}, "")' for x in f["fields"])
        routes += f'''
    @app.route("/{f["name"]}", methods=["POST"])
    def {f["name"]}(req):
        app.db.execute("INSERT INTO {f["name"]}({cols}) VALUES({marks})", [{vals}])
        return app.page(req, "Thank you", ui.alert({f["thanks"]!r}, "success"), ui.button("Back", "/"))
'''
    return f'''from kit import ui


def register(app):
    @app.route("/")
    def home(req):
        return app.page(req, "Welcome", {", ".join(parts)})
{routes}'''


def reference_files(spec):
    files = {"schema.py": schema_py(spec)}
    for e in spec["entities"]:
        files[f"pages/{e['name']}.py"] = entity_py(spec, e)
    if spec["kind"] == "app" and spec["dashboard"]:
        files["pages/dashboard.py"] = dashboard_py(spec)
    if spec["kind"] == "site":
        files["pages/home.py"] = home_py(spec)
    return files



def file_for(spec, task):
    """The template version of one task's file, or None if this task has no template."""
    files = reference_files(spec)
    return files.get(task["file"])
