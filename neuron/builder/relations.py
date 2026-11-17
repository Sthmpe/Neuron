"""Records that point at other records, and rules that change them.

Business apps need more than separate lists: a sale names a product, and adding the sale lowers
that product's stock; a loan names a book and lowers the copies available; a payment raises a
balance. This module adds two things to the build specification, and everything that follows
from them is ordinary code (contracts for the model, deterministic templates, acceptance checks):

  link field   {"name": "product", "type": "link", "to": "product"}
               a choice from the records of another entity. Stored as that record's key text
               (the other entity's search field, usually its name), shown as a drop-down.
  rule         {"on_add": "sale", "link_field": "product", "target_field": "stock",
                "amount_field": "quantity", "change": "subtract", "block_if_negative": true}
               when a record of `on_add` is added, the linked record's number field goes down
               (subtract) or up (add) by the amount; with block_if_negative the new record is
               refused, with a clear message, if the number would drop below zero.

Limits (stated, not hidden): links use the key text, so two records with the same key are not
told apart; one rule per added record type; amounts come from one number field.
"""
import copy

from .spec import SAMPLES, label, slug

RULE = {"type": "object", "required": ["on_add", "link_field", "target_field", "amount_field", "change", "block_if_negative"],
        "properties": {"on_add": {"type": "string"}, "link_field": {"type": "string"}, "target_field": {"type": "string"},
                       "amount_field": {"type": "string"}, "change": {"type": "string", "enum": ["subtract", "add"]},
                       "block_if_negative": {"type": "boolean"}}}
BIG = "1000"                  # starting amount for records that rules take from, in checks that are not about the rule


def extend_schema(schema):
    """The planner's JSON schema with link fields and rules added (rules optional)."""
    s = copy.deepcopy(schema)
    ent_field = s["properties"]["entities"]["items"]["properties"]["fields"]["items"]
    ent_field["properties"]["type"]["enum"] = list(ent_field["properties"]["type"]["enum"]) + ["link"]
    ent_field["properties"]["to"] = {"type": "string"}
    s["properties"]["rules"] = {"type": "array", "maxItems": 4, "items": RULE}
    return s


def apply(raw, s, problems):
    """Add link fields and rules from the planner's raw spec to the normalised spec `s` (in place)."""
    ents = {e["name"]: e for e in s.get("entities", [])}
    for re_ in raw.get("entities") if isinstance(raw.get("entities"), list) else []:
        if not isinstance(re_, dict) or slug(re_.get("name") or "") not in ents:
            continue
        e = ents[slug(re_["name"])]
        for rf in re_.get("fields") if isinstance(re_.get("fields"), list) else []:
            if not isinstance(rf, dict) or rf.get("type") != "link":
                continue
            f = next((x for x in e["fields"] if x["name"] == slug(rf.get("name") or "")), None)
            to = slug(rf.get("to") or rf.get("name") or "")
            if f is None:
                continue
            if to not in ents or to == e["name"]:
                problems.append(f"'{e['name']}.{f['name']}' links to unknown entity '{rf.get('to')}'")
                continue
            f.update(type="link", to=to)
    s["rules"] = []
    for r in raw.get("rules") if isinstance(raw.get("rules"), list) else []:
        if not isinstance(r, dict):
            continue
        on, lf, tf, af = (slug(r.get(k) or "") for k in ("on_add", "link_field", "target_field", "amount_field"))
        where = f"rule on adding '{r.get('on_add')}'"
        if on not in ents:
            problems.append(f"{where}: unknown entity")
            continue
        link = next((f for f in ents[on]["fields"] if f["name"] == lf and f["type"] == "link"), None)
        if not link:
            problems.append(f"{where}: '{r.get('link_field')}' is not a link field of {on}")
            continue
        target = ents[link["to"]]
        if not any(f["name"] == tf and f["type"] == "number" for f in target["fields"]):
            problems.append(f"{where}: '{r.get('target_field')}' is not a number field of {target['name']}")
            continue
        if not any(f["name"] == af and f["type"] == "number" for f in ents[on]["fields"]):
            problems.append(f"{where}: '{r.get('amount_field')}' is not a number field of {on}")
            continue
        if any(x["on_add"] == on for x in s["rules"]):
            problems.append(f"{where}: only one rule per kind of record")
            continue
        s["rules"].append({"on_add": on, "link_field": lf, "target": target["name"], "target_key": target["search_field"],
                           "target_field": tf, "amount_field": af, "change": r.get("change") if r.get("change") in ("subtract", "add") else "subtract",
                           "block_if_negative": bool(r.get("block_if_negative"))})
    return s


def rule_for(spec, entity_name):
    return next((r for r in spec.get("rules", []) if r["on_add"] == entity_name), None)


def links_of(entity):
    return [f for f in entity["fields"] if f["type"] == "link"]


def options_code(spec, f):
    """Python expression: the choices for a link field (keys of the other entity's records)."""
    key = next(e for e in spec["entities"] if e["name"] == f["to"])["search_field"]
    return f'[r["{key}"] for r in app.db.query("SELECT {key} FROM {f["to"]} ORDER BY {key}")]'


def ui_field_code(spec, f, input_type):
    if f["type"] == "link":
        return f'ui.select("{f["label"]}", "{f["name"]}", {options_code(spec, f)})'
    return f'ui.field("{f["label"]}", "{f["name"]}", type="{input_type}")'


def refusal(rule):
    return f"Not enough {label(rule['target_field']).lower()}"


def contract_lines(spec, e):
    """Extra contract lines for the page of entity `e` (empty when it has no links or rule)."""
    lines = []
    for f in links_of(e):
        lines.append(f'- the "{f["name"]}" input is a drop-down of existing {f["to"]} records: {ui_field_code(spec, f, "text")}')
    r = rule_for(spec, e["name"])
    if r:
        sign = "-" if r["change"] == "subtract" else "+"
        lines += [
            f'- POST, BEFORE inserting: key = req.form.get("{r["link_field"]}", ""); amount = float(req.form.get("{r["amount_field"]}") or 0)',
            f'  target = app.db.one("SELECT {r["target_field"]} FROM {r["target"]} WHERE {r["target_key"]} = ?", [key])',
            f'  if target is None: return app.page(req, "{e["label"]}", ui.alert("Choose a {r["target"].replace("_", " ")} that exists.", "error"), ui.button("Back", "/{e["name"]}"))',
            f'  new = (target["{r["target_field"]}"] or 0) {sign} amount',
        ]
        if r["block_if_negative"]:
            lines.append(f'  if new < 0: return app.page(req, "{e["label"]}", ui.alert("{refusal(r)}: only " + format(target["{r["target_field"]}"] or 0, "g") + " left.", "error"), ui.button("Back", "/{e["name"]}"))')
        lines.append(f'  after inserting: app.db.execute("UPDATE {r["target"]} SET {r["target_field"]} = ? WHERE {r["target_key"]} = ?", [new, key])')
    return lines


def template_post(spec, e, indent="            "):
    """Code that runs before the INSERT in the deterministic template (returns early on refusal)."""
    r = rule_for(spec, e["name"])
    if not r:
        return "", ""
    sign = "-" if r["change"] == "subtract" else "+"
    back = f'ui.button("Back", "/{e["name"]}")'
    pre = [f'key = req.form.get("{r["link_field"]}", "")',
           f'amount = float(req.form.get("{r["amount_field"]}") or 0)',
           f'target = app.db.one("SELECT {r["target_field"]} FROM {r["target"]} WHERE {r["target_key"]} = ?", [key])',
           "if target is None:",
           f'    return app.page(req, "{e["label"]}", ui.alert("Choose a {r["target"].replace("_", " ")} that exists.", "error"), {back})',
           f'new = (target["{r["target_field"]}"] or 0) {sign} amount']
    if r["block_if_negative"]:
        pre += ["if new < 0:",
                f'    return app.page(req, "{e["label"]}", ui.alert("{refusal(r)}: only " + format(target["{r["target_field"]}"] or 0, "g") + " left.", "error"), {back})']
    post = [f'app.db.execute("UPDATE {r["target"]} SET {r["target_field"]} = ? WHERE {r["target_key"]} = ?", [new, key])']
    return "\n".join(indent + x for x in pre) + "\n", "\n".join(indent + x for x in post) + "\n"


def sample(spec, e, n):
    """Sample form values for entity e: link fields point at the n-th sample record of their target."""
    row = {f["name"]: SAMPLES["text" if f["type"] == "link" else f["type"]][n] for f in e["fields"]}
    for f in links_of(e):
        target = next(x for x in spec["entities"] if x["name"] == f["to"])
        row[f["name"]] = SAMPLES[next(x["type"] for x in target["fields"] if x["name"] == target["search_field"])][n]
    return row


def setup_steps(spec, e):
    """Steps that create the records entity e's sample rows link to, with plenty of any amount rules take from."""
    steps = []
    for f in links_of(e):
        target = next(x for x in spec["entities"] if x["name"] == f["to"])
        r = rule_for(spec, e["name"])
        for n in (0, 1):
            row = sample(spec, target, n)
            if r and r["target"] == target["name"]:
                row[r["target_field"]] = BIG
            steps.append({"post": f"/{target['name']}", "form": row})
    return steps


def rule_checks(spec, auth):
    """One acceptance check per rule: the linked number really changes, and refusal works."""
    checks = []
    for r in spec.get("rules", []):
        target = next(x for x in spec["entities"] if x["name"] == r["target"])
        on = next(x for x in spec["entities"] if x["name"] == r["on_add"])
        key = sample(spec, target, 0)[r["target_key"]]
        t_row = dict(sample(spec, target, 0), **{r["target_field"]: "47"})
        add = dict(sample(spec, on, 0), **{r["link_field"]: key, r["amount_field"]: "5"})
        after = "42" if r["change"] == "subtract" else "52"
        steps = list(auth) + [{"post": f"/{target['name']}", "form": t_row}, {"post": f"/{on['name']}", "form": add},
                              {"get": f"/{target['name']}?q={key.split()[0]}", "expect_text": [key, after], "expect_no_text": ["47"]}]
        if r["block_if_negative"] and r["change"] == "subtract":
            too_much = dict(add, **{r["amount_field"]: "500"})
            steps += [{"post": f"/{on['name']}", "form": too_much, "expect_text": [refusal(r)]},
                      {"get": f"/{target['name']}?q={key.split()[0]}", "expect_text": [after]}]
        steps += [{"restart": True}, {"get": f"/{target['name']}?q={key.split()[0]}", "expect_text": [after]}]
        checks.append({"name": f"adding a {on['label'].lower()} {'lowers' if r['change'] == 'subtract' else 'raises'} the "
                               f"{target['label'].lower()}'s {label(r['target_field']).lower()}", "steps": steps})
    return checks
