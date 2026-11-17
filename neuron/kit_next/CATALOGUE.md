# NEURON kit: component catalogue (for the model; keep it short)

```python
from kit.web import redirect
from kit import ui
```
You decide WHAT to show. The theme decides HOW: layout, colours, fonts, spacing, icons.

Page      app.page(req, "Title", part, part, ...)
Hero      ui.hero(headline, subline, button_text, "#form-id")      first part of a home page; one per page
Section   ui.section(title, part, ..., id="name")
          with ui.grid(cards) -> shown as cards, list, rows, tiles or steps (theme picks)
          with one ui.text(...) -> shown as a callout, inline fact or panel (hours, price, place)
          with ui.form(...) -> shown beside the key facts, in a panel or on a band
Card      ui.card(title, ui.text("one short line"))                icon is picked from the title
Text      ui.text(words)   ui.alert(words, "success")   ui.button(words, "/path")   ui.badge(words)
Numbers   ui.stats(ui.stat("Label", value), ...)                    first number is the focal point
Data      ui.table(["Header", ...], rows)    ui.search("/path", q)
Forms     ui.form("/path", ui.field("Label", "name", type="text"), ..., submit="Send")
          types: text, email, tel, number, date, password;  ui.textarea, ui.select
Database  app.db.execute(sql, [values])   app.db.query(sql, [values]) -> list of dicts   app.db.value(sql)
Login     app.add_user(name, password); app.enable_login(); routes with login=True

Rules: never write HTML or CSS; use ? in SQL; short plain words; no em dashes.
