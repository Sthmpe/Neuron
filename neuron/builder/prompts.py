"""Fixed texts given to models: the kit guide and worked examples. No model names anywhere."""

KIT_GUIDE = '''# The NEURON kit (the only things you may use)

from kit.web import redirect
from kit import ui

app.db.execute(sql, [params])      change data (CREATE TABLE, INSERT, UPDATE, DELETE)
app.db.query(sql, [params])        read rows -> list of dicts, e.g. row["name"]
app.db.value(sql, [params])        read one value, e.g. a COUNT(*)
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
        return app.page(req, "Welcome",
                        ui.hero("Green Thumb Garden Care", "We keep your garden tidy all year.", "Get a quote", "#quotes"),
                        ui.section("What we do", ui.grid(ui.card("Mowing", ui.text("Weekly lawn cuts.")),
                                                         ui.card("Pruning", ui.text("Hedges and trees.")))),
                        ui.section("Where we work", ui.text("All of the east side.")),
                        ui.section("Ask for a quote", ui.form("/quotes", ui.field("Name", "name", type="text"),
                                                              ui.field("Phone", "phone", type="tel"), submit="Send"),
                                   id="quotes"))

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
- Use the owner's own words for names and labels. Do not invent features that were not asked for.'''

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
