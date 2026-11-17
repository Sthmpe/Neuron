"""The specification of a build, and how it is split into small tasks.

The planner model reads the owner's plain-language request and fills in this structure
(llama.cpp constrains its reply to the schema). Everything after that is ordinary code:
the spec is checked, then expanded into
  * a task list - one small file per task, each with an exact contract, and
  * acceptance checks for every task.
So the model decides WHAT is wanted; the system decides how the work is cut up and how each
piece is proven. This covers small sites and record-keeping apps (pages, forms, lists, search,
login, dashboard counts) - not arbitrary software.
"""
import re

FIELD = {"type": "object", "required": ["name", "type"],
         "properties": {"name": {"type": "string"},
                        "type": {"type": "string", "enum": ["text", "email", "phone", "number", "date"]}}}
SPEC_SCHEMA = {
    "type": "object",
    "required": ["app_name", "kind", "login_required", "username", "password", "home", "forms", "entities", "dashboard"],
    "properties": {
        "app_name": {"type": "string"},
        "kind": {"type": "string", "enum": ["site", "app"]},
        "login_required": {"type": "boolean"},
        "username": {"type": "string"},
        "password": {"type": "string"},
        "home": {"type": "object", "required": ["headline", "subheadline", "sections"],
                 "properties": {"headline": {"type": "string"}, "subheadline": {"type": "string"},
                                "sections": {"type": "array", "maxItems": 6, "items": {
                                    "type": "object", "required": ["title", "text", "items"],
                                    "properties": {"title": {"type": "string"}, "text": {"type": "string"},
                                                   "items": {"type": "array", "maxItems": 8, "items": {
                                                       "type": "object", "required": ["title", "text"],
                                                       "properties": {"title": {"type": "string"},
                                                                      "text": {"type": "string"}}}}}}}}},
        "forms": {"type": "array", "maxItems": 3, "items": {
            "type": "object", "required": ["name", "title", "fields", "button", "thanks"],
            "properties": {"name": {"type": "string"}, "title": {"type": "string"},
                           "fields": {"type": "array", "minItems": 1, "maxItems": 6, "items": FIELD},
                           "button": {"type": "string"}, "thanks": {"type": "string"}}}},
        "entities": {"type": "array", "maxItems": 5, "items": {
            "type": "object", "required": ["name", "fields", "search_field"],
            "properties": {"name": {"type": "string"},
                           "fields": {"type": "array", "minItems": 1, "maxItems": 8, "items": FIELD},
                           "search_field": {"type": "string"}}}},
        "dashboard": {"type": "array", "maxItems": 8, "items": {
            "type": "object", "required": ["label", "entity", "kind"],
            "properties": {"label": {"type": "string"}, "entity": {"type": "string"},
                           "kind": {"type": "string", "enum": ["count", "count_below"]},
                           "field": {"type": "string"}, "below": {"type": "number"}}}},
    },
}
SQL_TYPE = {"number": "REAL"}
INPUT_TYPE = {"text": "text", "email": "email", "phone": "tel", "number": "number", "date": "date"}
SAMPLES = {"text": ["Zed Alpha", "Kay Omega"], "email": ["zed@example.com", "kay@example.com"],
           "phone": ["0801 111 2222", "0802 333 4444"], "number": ["2", "70"], "date": ["2026-01-15", "2026-02-20"]}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "item"


def label(name):
    return str(name).replace("_", " ").strip().capitalize()


def normalise(spec):
    """Clean the planner's spec. Returns (spec, list of problems)."""
    problems = []
    if not isinstance(spec, dict):
        return {}, ["the specification must be a JSON object"]
    s = {"app_name": str(spec.get("app_name") or "").strip(), "kind": spec.get("kind"),
         "login_required": bool(spec.get("login_required")),
         "username": str(spec.get("username") or "").strip(), "password": str(spec.get("password") or "").strip()}
    if not s["app_name"]:
        problems.append("app_name is empty")
    if s["kind"] not in ("site", "app"):
        problems.append("kind must be 'site' or 'app'")

    def fields(raw, where):
        out, seen = [], set()
        for f in raw if isinstance(raw, list) else []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            name = slug(f["name"])
            if name in seen or name == "id":
                continue
            seen.add(name)
            out.append({"name": name, "label": label(f["name"]), "type": f.get("type") if f.get("type") in INPUT_TYPE else "text"})
        if not out:
            problems.append(f"{where} has no fields")
        return out

    home = spec.get("home") if isinstance(spec.get("home"), dict) else {}
    s["home"] = {"headline": str(home.get("headline") or "").strip(), "subheadline": str(home.get("subheadline") or "").strip(),
                 "sections": []}
    for sec in home.get("sections") if isinstance(home.get("sections"), list) else []:
        if isinstance(sec, dict) and str(sec.get("title") or "").strip():
            items = [{"title": str(i.get("title") or "").strip(), "text": str(i.get("text") or "").strip()}
                     for i in (sec.get("items") if isinstance(sec.get("items"), list) else [])
                     if isinstance(i, dict) and str(i.get("title") or "").strip()]
            s["home"]["sections"].append({"title": str(sec["title"]).strip(), "text": str(sec.get("text") or "").strip(),
                                          "items": items})
    s["forms"] = []
    for f in spec.get("forms") if isinstance(spec.get("forms"), list) else []:
        if isinstance(f, dict) and f.get("name"):
            name = slug(f["name"])
            s["forms"].append({"name": name, "title": str(f.get("title") or label(name)).strip(),
                               "fields": fields(f.get("fields"), f"form '{name}'"),
                               "button": str(f.get("button") or "Send").strip(),
                               "thanks": str(f.get("thanks") or "Thank you!").strip()})
    s["entities"] = []
    for e in spec.get("entities") if isinstance(spec.get("entities"), list) else []:
        if isinstance(e, dict) and e.get("name"):
            name = slug(e["name"])
            fs = fields(e.get("fields"), f"'{name}'")
            names = [f["name"] for f in fs]
            search = slug(e.get("search_field") or "")
            s["entities"].append({"name": name, "label": label(name), "fields": fs,
                                  "search_field": search if search in names else (names[0] if names else "")})
    ents = {e["name"]: e for e in s["entities"]}
    s["dashboard"] = []
    for d in spec.get("dashboard") if isinstance(spec.get("dashboard"), list) else []:
        if not isinstance(d, dict) or not d.get("label"):
            continue
        ent = slug(d.get("entity") or "")
        if ent not in ents:
            problems.append(f"dashboard item '{d['label']}' refers to unknown entity '{d.get('entity')}'")
            continue
        item = {"label": str(d["label"]).strip(), "entity": ent, "kind": d.get("kind") if d.get("kind") in ("count", "count_below") else "count"}
        if item["kind"] == "count_below":
            f = slug(d.get("field") or "")
            numeric = [x["name"] for x in ents[ent]["fields"] if x["type"] == "number"]
            if f not in numeric or not isinstance(d.get("below"), (int, float)) or isinstance(d.get("below"), bool):
                problems.append(f"dashboard item '{item['label']}' needs a number field of {ent} and a 'below' number")
                continue
            item.update(field=f, below=d["below"])
        s["dashboard"].append(item)
    if s["kind"] == "app":
        if not s["entities"]:
            problems.append("an app needs at least one entity (a kind of record to keep)")
        if s["login_required"] and not (s["username"] and s["password"]):
            problems.append("login_required is true but username or password is empty - copy both exactly from the request")
    if s["kind"] == "site" and not s["home"]["headline"]:
        problems.append("a site needs home.headline")
    return s, problems


def _table_sql(name, fs):
    cols = ", ".join(f"{f['name']} {SQL_TYPE.get(f['type'], 'TEXT')}" for f in fs)
    return f"{name}(id INTEGER PRIMARY KEY, {cols})"


def _ui_fields(fs):
    return ", ".join(f'ui.field("{f["label"]}", "{f["name"]}", type="{INPUT_TYPE[f["type"]]}")' for f in fs)


def _sample(fs, n):
    return {f["name"]: SAMPLES[f["type"]][n] for f in fs}


def expand(spec):
    """Spec -> (tasks, acceptance checks, file purposes). Deterministic: no model involved."""
    tasks, checks, purposes = [], [], {"app.py": "Starts the app. Generated - never edit."}
    login = spec["kind"] == "app" and spec["login_required"]
    creds = {"username": spec["username"], "password": spec["password"]}
    auth = [{"login": creds}] if login else []
    flag = ", login=True" if login else ""

    def add(task, task_checks):
        for c in task_checks:
            c["task"] = task["id"]
            checks.append(c)
        task["checks"] = [c["name"] for c in task_checks]
        purposes[task["file"]] = task["title"]
        tasks.append(task)

    # ---- schema ----------------------------------------------------------
    tables = [_table_sql(e["name"], e["fields"]) for e in spec["entities"]] + \
             [_table_sql(f["name"], f["fields"]) for f in spec["forms"]]
    if spec["kind"] == "app":
        nav = ([("Dashboard", "/")] if spec["dashboard"] else []) + [(e["label"], "/" + e["name"]) for e in spec["entities"]]
    else:
        nav = [("Home", "/")]
    lines = ["Write schema.py. It must define exactly one function: setup(app). Inside it:"]
    lines += [f'- app.db.execute("CREATE TABLE IF NOT EXISTS {t}")' for t in tables]
    if login:
        lines += [f'- app.add_user("{creds["username"]}", "{creds["password"]}")', "- app.enable_login()"]
    lines.append(f"- app.nav = {nav!r}")
    lines.append("Use these exact table and column names. Do not add routes here.")
    add({"id": "schema", "title": "Database tables" + (", first user and login" if login else "") + ", menu",
         "file": "schema.py", "must_define": "setup", "contract": "\n".join(lines), "needs": [], "example": "schema"},
        [{"name": "app starts", "steps": ([{"get": "/login", "expect_text": ["Log in"]}, {"login": creds}] if login
                                          else [{"get": "/static/neuron.css"}])}])

    # ---- one page per entity ---------------------------------------------
    for e in spec["entities"]:
        n, fs, sf = e["name"], e["fields"], e["search_field"]
        cols = ", ".join(f["name"] for f in fs)
        a, b = _sample(fs, 0), _sample(fs, 1)
        contract = "\n".join([
            f"Write pages/{n}.py. It must define register(app), which adds ONE route:",
            f'@app.route("/{n}", methods=["GET", "POST"]{flag})',
            f"- POST: insert a row into table {n} (columns: {cols}) from req.form, then return redirect(\"/{n}\").",
            f'- GET: q = req.query.get("q", ""). Select rows from {n} where {sf} LIKE "%q%", newest first (ORDER BY id DESC).',
            f'  Return app.page(req, "{e["label"]}", ui.search("/{n}", q), ui.table([{", ".join(repr(f["label"]) for f in fs)}], rows),',
            f'  ui.card("Add {e["label"].lower()}", ui.form("/{n}", {_ui_fields(fs)}, submit="Add")))',
            "  where rows is a list of lists with one value per column, in that order.",
        ])
        steps = ([{"get": f"/{n}", "expect_redirect": "/login"}] if login else []) + auth + [
            {"get": f"/{n}", "expect_text": [e["label"]] + [f["label"] for f in fs]},
            {"post": f"/{n}", "form": a}, {"post": f"/{n}", "form": b},
            {"get": f"/{n}", "expect_text": [a[sf], b[sf]]},
            {"get": f"/{n}?q={a[sf].split()[0]}", "expect_text": [a[sf]], "expect_no_text": [b[sf]]},
            {"restart": True}, {"get": f"/{n}", "expect_text": [a[sf], b[sf]]}]
        add({"id": n, "title": f"{e['label']} page: list, search, add", "file": f"pages/{n}.py", "must_define": "register",
             "contract": contract, "needs": ["schema.py"], "example": "entity"},
            [{"name": f"{n}: add, list, search, survive restart", "steps": steps}])

    # ---- dashboard --------------------------------------------------------
    if spec["kind"] == "app" and spec["dashboard"]:
        lines = ["Write pages/dashboard.py. It must define register(app), which adds ONE route:",
                 f'@app.route("/"{flag})', "It shows these numbers with ui.stats(ui.stat(label, value), ...):"]
        expect = []
        ents = {e["name"]: e for e in spec["entities"]}
        for d in spec["dashboard"]:
            if d["kind"] == "count":
                lines.append(f'- "{d["label"]}": app.db.value("SELECT COUNT(*) FROM {d["entity"]}")')
                expect.append([d["label"], "2"])
            else:
                lines.append(f'- "{d["label"]}": app.db.value("SELECT COUNT(*) FROM {d["entity"]} WHERE {d["field"]} < {d["below"]:g}")')
                expect.append([d["label"], None, d])
        lines.append('Return app.page(req, "Dashboard", ui.stats(...)).')
        steps = ([{"get": "/", "expect_redirect": "/login"}] if login else []) + auth
        for e in spec["entities"]:
            rows = [_sample(e["fields"], 0), _sample(e["fields"], 1)]
            for d in spec["dashboard"]:
                if d["kind"] == "count_below" and d["entity"] == e["name"]:
                    rows[0][d["field"]] = str(int(d["below"]) - 1)
                    rows[1][d["field"]] = str(int(d["below"]) + 50)
            steps += [{"post": f"/{e['name']}", "form": r} for r in rows]
        near = [[x[0], x[1] if x[1] else "1"] for x in expect]
        steps.append({"get": "/", "expect_text": [d["label"] for d in spec["dashboard"]], "expect_near": near})
        add({"id": "dashboard", "title": "Dashboard with the key numbers", "file": "pages/dashboard.py",
             "must_define": "register", "contract": "\n".join(lines),
             "needs": ["schema.py"] + [f"pages/{e['name']}.py" for e in spec["entities"]], "example": "dashboard"},
            [{"name": "dashboard numbers", "steps": steps}])

    # ---- home page of a site ----------------------------------------------
    if spec["kind"] == "site":
        h = spec["home"]
        lines = ["Write pages/home.py. It must define register(app). Routes:", '@app.route("/")',
                 'Return app.page(req, title, ...) built from these parts, in this order:',
                 f'- ui.hero("{h["headline"]}", "{h["subheadline"]}"' +
                 (f', "{spec["forms"][0]["button"]}", "#{spec["forms"][0]["name"]}")' if spec["forms"] else ")")]
        must_show = [h["headline"]]
        for sec in h["sections"]:
            if sec["items"]:
                lines.append(f'- ui.section("{sec["title"]}", ui.grid(' +
                             ", ".join(f'ui.card("{i["title"]}", ui.text("{i["text"]}"))' for i in sec["items"]) + "))")
                must_show += [sec["title"]] + [i["title"] for i in sec["items"]]
            else:
                lines.append(f'- ui.section("{sec["title"]}", ui.text("{sec["text"]}"))')
                must_show.append(sec["title"])
        form_checks = []
        for f in spec["forms"]:
            cols = ", ".join(x["name"] for x in f["fields"])
            lines.append(f'- ui.section("{f["title"]}", ui.form("/{f["name"]}", {_ui_fields(f["fields"])}, submit="{f["button"]}"), id="{f["name"]}")')
            lines.append(f'@app.route("/{f["name"]}", methods=["POST"])')
            lines.append(f'- insert a row into table {f["name"]} (columns: {cols}) from req.form, then return '
                         f'app.page(req, "Thank you", ui.alert("{f["thanks"]}", "success"), ui.button("Back", "/"))')
            must_show.append(f["title"])
            form_checks.append({"post": f"/{f['name']}", "form": _sample(f["fields"], 0), "expect_text": [f["thanks"]]})
        lines.append("Keep every text exactly as written above.")
        add({"id": "home", "title": "Home page" + (" and its form" if spec["forms"] else ""), "file": "pages/home.py",
             "must_define": "register", "contract": "\n".join(lines), "needs": ["schema.py"], "example": "home",
             "review": True},
            [{"name": "home page content and form", "steps": [{"get": "/", "expect_text": must_show}] + form_checks +
              [{"restart": True}, {"get": "/", "expect_text": must_show[:1]}]}])
    return tasks, checks, purposes
