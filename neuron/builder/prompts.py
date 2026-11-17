"""Fixed texts given to models: the kit guide and worked examples. No model names anywhere."""

KIT_GUIDE = '''# The NEURON kit (the only things you may use)

from kit.web import redirect
from kit import ui

app.db.execute(sql, [params])      change data (CREATE TABLE, INSERT, UPDATE, DELETE)
app.db.query(sql, [params])        read rows -> list of dicts, e.g. row["name"]
app.db.value(sql, [params])        read one value, e.g. a COUNT(*)
app.db.one(sql, [params])          read one row -> dict, or None if there is none
app.add_user(username, password)   create the first user
app.enable_login()                 adds /login and /logout
app.nav = [("Label", "/path")]     the menu
@app.route("/path", methods=["GET", "POST"], login=True)   a page; the function gets req
req.method   req.form.get("name", "")   req.query.get("q", "")   req.user
redirect("/path")                  go to another page (after a POST)
app.page(req, "Title", part, part, ...)   a full page in the shared layout

ui parts (each returns HTML; plain text is escaped for you):
ui.hero(title, subtitle, button_text, button_href)   ui.section(title, part, ..., id="name")
ui.grid(card, card, ...)   ui.card(title, part, ...)   ui.text("words")   ui.alert("words", "success")
ui.button("words", "/path")   ui.stats(ui.stat("Label", value), ...)
ui.table(["Header", ...], rows)        rows = list of lists
ui.form("/path", field, ..., submit="Save")   ui.field("Label", "name", type="text")
ui.select("Label", "name", ["choice", ...])   a drop-down
ui.search("/path", q)
Never write raw HTML or CSS. Always use ? placeholders in SQL.'''

EXAMPLES = {
    "schema": '''# schema.py
def setup(app):
    app.db.execute("CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY, title TEXT, author TEXT, pages REAL)")
    app.add_user("librarian", "quiet55")
    app.enable_login()
    app.nav = [("Dashboard", "/"), ("Books", "/books")]
''',
    "entity": '''# pages/books.py
from kit.web import redirect
from kit import ui


def register(app):
    @app.route("/books", methods=["GET", "POST"], login=True)
    def books(req):
        if req.method == "POST":
            app.db.execute("INSERT INTO books(title, author, pages) VALUES(?, ?, ?)",
                           [req.form.get("title", ""), req.form.get("author", ""), req.form.get("pages", "")])
            return redirect("/books")
        q = req.query.get("q", "")
        found = app.db.query("SELECT * FROM books WHERE title LIKE ? ORDER BY id DESC", ["%" + q + "%"])
        rows = [[b["title"], b["author"], b["pages"]] for b in found]
        return app.page(req, "Books", ui.search("/books", q), ui.table(["Title", "Author", "Pages"], rows),
                        ui.card("Add book", ui.form("/books", ui.field("Title", "title", type="text"),
                                                    ui.field("Author", "author", type="text"),
                                                    ui.field("Pages", "pages", type="number"), submit="Add")))
''',
    "entity_link": '''# pages/hires.py  (a hire names a tool; adding one lowers the tool's in_store, refused below zero)
from kit.web import redirect
from kit import ui


def register(app):
    @app.route("/hires", methods=["GET", "POST"], login=True)
    def hires(req):
        if req.method == "POST":
            key = req.form.get("tool", "")
            amount = float(req.form.get("quantity") or 0)
            target = app.db.one("SELECT in_store FROM tools WHERE name = ?", [key])
            if target is None:
                return app.page(req, "Hires", ui.alert("Choose one of the tools listed.", "error"), ui.button("Back", "/hires"))
            new = (target["in_store"] or 0) - amount
            if new < 0:
                return app.page(req, "Hires", ui.alert("Not enough in store: only " + format(target["in_store"] or 0, "g") + " left.", "error"),
                                ui.button("Back", "/hires"))
            app.db.execute("INSERT INTO hires(tool, quantity, customer) VALUES(?, ?, ?)",
                           [key, req.form.get("quantity", ""), req.form.get("customer", "")])
            app.db.execute("UPDATE tools SET in_store = ? WHERE name = ?", [new, key])
            return redirect("/hires")
        q = req.query.get("q", "")
        found = app.db.query("SELECT * FROM hires WHERE customer LIKE ? ORDER BY id DESC", ["%" + q + "%"])
        rows = [[h["tool"], h["quantity"], h["customer"]] for h in found]
        tools = [t["name"] for t in app.db.query("SELECT name FROM tools ORDER BY name")]
        return app.page(req, "Hires", ui.search("/hires", q), ui.table(["Tool", "Quantity", "Customer"], rows),
                        ui.card("Add hire", ui.form("/hires", ui.select("Tool", "tool", tools),
                                                    ui.field("Quantity", "quantity", type="number"),
                                                    ui.field("Customer", "customer", type="text"), submit="Add")))
''',
    "dashboard": '''# pages/dashboard.py
from kit import ui


def register(app):
    @app.route("/", login=True)
    def dashboard(req):
        books = app.db.value("SELECT COUNT(*) FROM books")
        short = app.db.value("SELECT COUNT(*) FROM books WHERE pages < 100")
        return app.page(req, "Dashboard", ui.stats(ui.stat("Books", books), ui.stat("Short books", short)))
''',
    "home": '''# pages/home.py
from kit import ui


def register(app):
    @app.route("/")
    def home(req):
        parts = []
        parts.append(ui.hero("Green Thumb Garden Care", "We keep your garden tidy all year.", "Get a quote", "#quotes"))
        parts.append(ui.section("What we do", ui.grid(ui.card("Mowing", ui.text("Weekly lawn cuts.")),
                                                      ui.card("Pruning", ui.text("Hedges and trees.")))))
        parts.append(ui.section("Where we work", ui.text("All of the east side.")))
        parts.append(ui.section("Ask for a quote", ui.form("/quotes", ui.field("Name", "name", type="text"),
                                                           ui.field("Phone", "phone", type="tel"), submit="Send"), id="quotes"))
        return app.page(req, "Welcome", *parts)

    @app.route("/quotes", methods=["POST"])
    def quotes(req):
        app.db.execute("INSERT INTO quotes(name, phone) VALUES(?, ?)", [req.form.get("name", ""), req.form.get("phone", "")])
        return app.page(req, "Thank you", ui.alert("Thanks, we will call you back.", "success"), ui.button("Back", "/"))
''',
}

PLANNER_SYSTEM = '''You turn a plain-language request for a small website or app into a specification, as JSON.
Rules:
- kind is "site" for a public page that presents something (with or without a form); "app" when the owner logs in and keeps records.
- For a site: fill home.headline (include the business name), home.subheadline, and one section per thing the
  request asks to show. A section that lists several things has one item per thing (title + one short line).
  A section with a single fact has text and no items. Every form the request asks for goes in "forms"
  (name: one lowercase word, fields, button text, thanks message). Leave entities and dashboard empty.
- For an app: one entity per kind of record (name: lowercase plural, e.g. "customers"), its fields with types
  (text, email, phone, number, date), and the field people search by. One dashboard item per number the owner
  wants to see: kind "count" for "how many", kind "count_below" with field and below for "how many have less
  than N". Copy the username and password exactly from the request. Leave home sections and forms empty.
- When one kind of record names another (a hire names a tool), give it a field of type "link" with "to" set to
  the other entity's name. When adding a record must change a number on the record it names (stock goes down,
  a balance goes up), add a rule: on_add (the entity being added), link_field, target_field (the number that
  changes), amount_field (the number in the added record), change "subtract" or "add", and block_if_negative
  true if the owner wants it refused when not enough is left. Add no rules that were not asked for.
- Labels must use the owner's own words: if they ask "how many students are under 18", the label is "Under 18".
- Do not invent sections, forms or features that were not asked for.'''

PLANNER_SITE_REQUEST = ("I need a simple web page for my garden care business, Green Thumb Garden Care. Put the name in a big "
                        "headline, show the two things we do - mowing and pruning - with a line about each, say that we work "
                        "all over the east side, and add a form where people leave their name and phone to ask for a quote. "
                        "Thank them afterwards.")
PLANNER_SITE_SPEC = {
    "app_name": "Green Thumb Garden Care", "kind": "site", "login_required": False, "username": "", "password": "",
    "home": {"headline": "Green Thumb Garden Care", "subheadline": "We keep your garden tidy all year.", "sections": [
        {"title": "What we do", "text": "", "items": [{"title": "Mowing", "text": "Weekly lawn cuts."},
                                                      {"title": "Pruning", "text": "Hedges and trees."}]},
        {"title": "Where we work", "text": "All over the east side.", "items": []}]},
    "forms": [{"name": "quotes", "title": "Ask for a quote", "fields": [{"name": "name", "type": "text"},
                                                                        {"name": "phone", "type": "phone"}],
               "button": "Send", "thanks": "Thank you, we will call you back."}],
    "entities": [], "dashboard": []}

PLANNER_EXAMPLE_REQUEST = ("I run a small library. I want an app where I log in (user librarian, password quiet55) and keep a "
                           "list of books with title, author and number of pages. I want to search books by title and see "
                           "on a dashboard how many books I have and how many have fewer than 100 pages.")
PLANNER_EXAMPLE_SPEC = {
    "app_name": "Library", "kind": "app", "login_required": True, "username": "librarian", "password": "quiet55",
    "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
    "entities": [{"name": "books", "fields": [{"name": "title", "type": "text"}, {"name": "author", "type": "text"},
                                               {"name": "pages", "type": "number"}], "search_field": "title"}],
    "dashboard": [{"label": "Books", "entity": "books", "kind": "count"},
                  {"label": "Short books", "entity": "books", "kind": "count_below", "field": "pages", "below": 100}]}

PLANNER_RULE_REQUEST = ("I hire out garden tools. App with login (user tools, password rake2024). Keep my tools with their "
                        "name and how many are in store. Keep hires: which tool, how many, and the customer's name. When I add "
                        "a hire, the number in store for that tool must go down, and the hire must be refused if not enough "
                        "are in store. Search hires by customer.")
PLANNER_RULE_SPEC = {
    "app_name": "Tool Hire", "kind": "app", "login_required": True, "username": "tools", "password": "rake2024",
    "home": {"headline": "", "subheadline": "", "sections": []}, "forms": [],
    "entities": [{"name": "tools", "fields": [{"name": "name", "type": "text"}, {"name": "in_store", "type": "number"}],
                  "search_field": "name"},
                 {"name": "hires", "fields": [{"name": "tool", "type": "link", "to": "tools"}, {"name": "quantity", "type": "number"},
                                              {"name": "customer", "type": "text"}], "search_field": "customer"}],
    "dashboard": [],
    "rules": [{"on_add": "hires", "link_field": "tool", "target_field": "in_store", "amount_field": "quantity",
               "change": "subtract", "block_if_negative": True}]}

BUILDER_SYSTEM = ("You write one small Python file for a web app built with the NEURON kit. Follow the contract exactly. "
                  "Use only the kit functions shown. Reply with one ```python block that contains the complete file, "
                  "and nothing else.")
REVIEWER_SYSTEM = ("You are a careful code reviewer. A file failed its check. Say in at most three sentences what is "
                   "wrong and exactly what to change. Do not write the whole file.")
CONTENT_REVIEW_SYSTEM = ("You check a web page against what the owner asked for. Reply with JSON: "
                         '{"ok": true or false, "missing": ["each thing the owner asked for that the page does not show"]}. '
                         "Only list things the owner clearly asked for.")

BASE_SYSTEM = ("You write small web apps with the NEURON kit. Use only the kit functions shown. "
               "Reply with the files, each as a line 'FILE: <path>' followed by one ```python block with the complete file.")
BASE_TASK = '''Build what the owner asks for, using the kit.
Write these files: schema.py (function setup(app): tables, first user and login if needed, app.nav, and app.name = "<name>")
and one file per page in pages/ (each with a function register(app) that adds its routes). The page at "/" is the home page.
The file app.py already exists and calls schema.setup(app) and every pages/*.py register(app).

The owner's request:
'''

DIAGNOSE_SYSTEM = ("You are a careful Python reviewer. The project's tests fail because of ONE bug in the source code "
                   "(the tests are correct). Work out which function contains the bug. Reply with JSON: "
                   '{"function": "<name from the list>", "problem": "<what the code does wrong>", "fix": "<exactly what to change>"}')
FIX_SYSTEM = ("You are a careful Python programmer. Rewrite ONE function to fix the bug described. Change as little as "
              "possible and keep its name and arguments. Reply with one ```python block containing only the complete "
              "corrected function.")

EDIT_SYSTEM = ("You are a careful Python programmer. Fix the bug described by changing as few lines as possible. "
               "Reply with exactly two code blocks: first the line(s) to replace, copied exactly from the function; "
               "then the corrected line(s).")
EDIT_FORMAT = """
Reply in exactly this format:
OLD:
```python
<the faulty line or lines, copied exactly from the function above>
```
NEW:
```python
<the corrected line or lines>
```"""
