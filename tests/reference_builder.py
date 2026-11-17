"""Reference specs for tests, plus the deterministic templates (now part of the system in
neuron/builder/templates.py). Used to prove every benchmark examiner CAN be passed by a correct app,
and as scripted replies in builder tests. Never used to produce a score."""
from neuron.builder.templates import dashboard_py, entity_py, home_py, reference_files, schema_py  # noqa: F401

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
