"""A reference 'builder' for tests: writes correct files straight from a spec, with no model.
It is used (a) as the scripted replies of the test double in builder tests and (b) to prove that
every benchmark examiner CAN be passed by a correct app. It is never used to produce a score."""
from neuron.builder.spec import INPUT_TYPE, SQL_TYPE


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
    row = ", ".join(f'r[{f["name"]!r}]' for f in e["fields"])
    return f'''from kit.web import redirect
from kit import ui


def register(app):
    @app.route("/{e["name"]}", methods=["GET", "POST"]{login})
    def {e["name"]}(req):
        if req.method == "POST":
            app.db.execute("INSERT INTO {e["name"]}({cols}) VALUES({marks})", [{vals}])
            return redirect("/{e["name"]}")
        q = req.query.get("q", "")
        found = app.db.query("SELECT * FROM {e["name"]} WHERE {e["search_field"]} LIKE ? ORDER BY id DESC", ["%" + q + "%"])
        rows = [[{row}] for r in found]
        return app.page(req, {e["label"]!r}, ui.search("/{e["name"]}", q), ui.table({[f["label"] for f in e["fields"]]!r}, rows),
                        ui.card("Add", ui.form("/{e["name"]}", {_fields(e["fields"])}, submit="Add")))
'''


def dashboard_py(spec):
    login = ", login=True" if spec["login_required"] else ""
    stats = []
    for d in spec["dashboard"]:
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


F = lambda name, type="text": {"name": name, "type": type}
EMPTY_HOME = {"headline": "", "subheadline": "", "sections": []}
REFERENCE_SPECS = {
    "d1_tutor_site": {"app_name": "BrightPath Tutors", "kind": "site", "login_required": False, "forms": [
        {"name": "callbacks", "title": "Ask for a call back", "fields": [F("name"), F("phone", "phone")], "button": "Send", "thanks": "Thank you, we will call you back."}],
        "home": {"headline": "BrightPath Tutors", "subheadline": "Friendly lessons that work.", "sections": [
            {"title": "Subjects", "text": "", "items": [{"title": "Maths", "text": "Numbers made simple."}, {"title": "Physics", "text": "How things work."}, {"title": "English", "text": "Read and write well."}]},
            {"title": "Price", "text": "5,000 naira per lesson.", "items": []}]}, "entities": [], "dashboard": []},
    "d2_class_app": {"app_name": "Evening Classes", "kind": "app", "login_required": True, "username": "teacher", "password": "chalk77",
        "home": EMPTY_HOME, "forms": [], "entities": [
            {"name": "students", "fields": [F("name"), F("email", "email"), F("age", "number")], "search_field": "name"},
            {"name": "courses", "fields": [F("title"), F("fee", "number")], "search_field": "title"}],
        "dashboard": [{"label": "Students", "entity": "students", "kind": "count"}, {"label": "Courses", "entity": "courses", "kind": "count"},
                      {"label": "Under 18", "entity": "students", "kind": "count_below", "field": "age", "below": 18}]},
    "b1_bakery_landing": {"app_name": "Sunrise Bakery", "kind": "site", "login_required": False, "forms": [
        {"name": "subscribers", "title": "Hear about new offers", "fields": [F("email", "email")], "button": "Sign up", "thanks": "Thank you for signing up!"}],
        "home": {"headline": "Welcome to Sunrise Bakery", "subheadline": "Baked fresh in Ibadan every morning.", "sections": [
            {"title": "What we sell", "text": "", "items": [{"title": "Fresh bread", "text": "Warm every morning."}, {"title": "Birthday cakes", "text": "Made to order."}, {"title": "Meat pies", "text": "Golden and filling."}]},
            {"title": "Opening hours", "text": "Monday to Saturday, 7am to 7pm.", "items": []}]}, "entities": [], "dashboard": []},
    "b2_shop_app": {"app_name": "My Shop", "kind": "app", "login_required": True, "username": "owner", "password": "sunrise42",
        "home": EMPTY_HOME, "forms": [], "entities": [
            {"name": "customers", "fields": [F("name"), F("phone", "phone"), F("email", "email")], "search_field": "name"},
            {"name": "products", "fields": [F("name"), F("price", "number"), F("quantity", "number")], "search_field": "name"}],
        "dashboard": [{"label": "Customers", "entity": "customers", "kind": "count"}, {"label": "Products", "entity": "products", "kind": "count"},
                      {"label": "Low stock", "entity": "products", "kind": "count_below", "field": "quantity", "below": 5}]},
}
REFERENCE_SPECS["b3_shop_app_resumed"] = REFERENCE_SPECS["b2_shop_app"]
