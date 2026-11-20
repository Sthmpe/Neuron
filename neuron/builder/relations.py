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

from .spec import SAMPLES, label, safe_name, slug

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
        if not isinstance(re_, dict) or safe_name(slug(re_.get("name") or ""), "list") not in ents:
            continue
        e = ents[safe_name(slug(re_["name"]), "list")]
        for rf in re_.get("fields") if isinstance(re_.get("fields"), list) else []:
            if not isinstance(rf, dict) or rf.get("type") != "link":
                continue
            f = next((x for x in e["fields"] if x["name"] == safe_name(slug(rf.get("name") or ""), "value")), None)
            to = safe_name(slug(rf.get("to") or rf.get("name") or ""), "list")
            if f is None:
                continue
            if to not in ents or to == e["name"]:
                s.setdefault("dropped", []).append(f"'{e['name']}.{f['name']}' links to unknown entity '{rf.get('to')}'; kept as text")
                continue
            f.update(type="link", to=to)
    s["rules"] = []
    for r in raw.get("rules") if isinstance(raw.get("rules"), list) else []:
        if not isinstance(r, dict):
            continue
        on = safe_name(slug(r.get("on_add") or ""), "list")
        lf, tf, af = (safe_name(slug(r.get(k) or ""), "value") for k in ("link_field", "target_field", "amount_field"))
        where = f"rule on adding '{r.get('on_add')}'"
        if on not in ents:
            s.setdefault("dropped", []).append(f"{where}: unknown entity")
            continue
        link = next((f for f in ents[on]["fields"] if f["name"] == lf and f["type"] == "link"), None)
        if not link:
            s.setdefault("dropped", []).append(f"{where}: '{r.get('link_field')}' is not a link field of {on}")
            continue
        target = ents[link["to"]]
        if not any(f["name"] == tf and f["type"] == "number" for f in target["fields"]):
            s.setdefault("dropped", []).append(f"{where}: '{r.get('target_field')}' is not a number field of {target['name']}")
            continue
        if not any(f["name"] == af and f["type"] == "number" for f in ents[on]["fields"]):
            s.setdefault("dropped", []).append(f"{where}: '{r.get('amount_field')}' is not a number field of {on}")
            continue
        if any(x["on_add"] == on for x in s["rules"]):
            s.setdefault("dropped", []).append(f"{where}: only one rule per kind of record")
            continue
        s["rules"].append({"on_add": on, "link_field": lf, "target": target["name"], "target_key": target["search_field"],
                           "target_field": tf, "amount_field": af, "change": r.get("change") if r.get("change") in ("subtract", "add") else "subtract",
                           "block_if_negative": bool(r.get("block_if_negative"))})
    return s


CHANGE_WORDS = r"\b(go(es)? down|go(es)? up|reduc\w*|decreas\w*|lower\w*|increas\w*|subtract\w*|deduct\w*|take\w* (off|away|from)|add\w* to the|balance|in stock|left in|remaining)\b"


def dropped_gaps(request, spec):
    """Invalid links or rules are dropped instead of rejecting the whole plan (small models invent rules nobody asked
    for: the 2 GB rerun of the held-out shop builds failed at planning this way). If the request does ask for a number
    to change, a dropped rule is reported as not built."""
    import re
    dropped = [d for d in spec.get("dropped", []) if d.startswith("rule")]
    if dropped and re.search(CHANGE_WORDS, request or "", re.I) and not spec.get("rules"):
        return ["a rule that changes one record when another is added (it could not be set up from the plan)"]
    return []


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
            f'  if target is None: return app.page(req, "{e["label"]}", ui.alert("Choose one of the {r["target"].replace("_", " ")} listed.", "error"), ui.button("Back", "/{e["name"]}"))',
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
           f'    return app.page(req, "{e["label"]}", ui.alert("Choose one of the {r["target"].replace("_", " ")} listed.", "error"), {back})',
           f'new = (target["{r["target_field"]}"] or 0) {sign} amount']
    if r["block_if_negative"]:
        pre += ["if new < 0:",
                f'    return app.page(req, "{e["label"]}", ui.alert("{refusal(r)}: only " + format(target["{r["target_field"]}"] or 0, "g") + " left.", "error"), {back})']
    post = [f'app.db.execute("UPDATE {r["target"]} SET {r["target_field"]} = ? WHERE {r["target_key"]} = ?", [new, key])']
    return "\n".join(indent + x for x in pre) + "\n", "\n".join(indent + x for x in post) + "\n"


LINK_KEYS = ["Brass Lamp", "Cedar Chair"]   # names for records others link to: different from the usual samples,
                                           # so a drop-down of them never looks like a search result


def _is_target(spec, name):
    return any(f.get("to") == name for e in spec["entities"] for f in links_of(e))


def _key_value(target, n):
    kind = next(x["type"] for x in target["fields"] if x["name"] == target["search_field"])
    return LINK_KEYS[n] if kind == "text" else SAMPLES[kind][n]


def sample(spec, e, n):
    """Sample form values for entity e. Records others link to get their own key names; link fields point at
    the n-th of those."""
    row = {f["name"]: SAMPLES["text" if f["type"] == "link" else f["type"]][n] for f in e["fields"]}
    if _is_target(spec, e["name"]):
        row[e["search_field"]] = _key_value(e, n)
    for f in links_of(e):
        row[f["name"]] = _key_value(next(x for x in spec["entities"] if x["name"] == f["to"]), n)
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


def rule_checks(spec, auth, on_add=None):
    """One acceptance check per rule (only the rule for `on_add` if given): the linked number really changes,
    and refusal works."""
    checks = []
    for r in spec.get("rules", []):
        if on_add and r["on_add"] != on_add:
            continue
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


AMOUNT_NAMES = r"quantit|qty|amount|units?|copies|seats|tickets|number|count|pieces|items|taken|sold|bought|out"
STOCK_NAMES = r"stock|copies|seats|units|left|available|on_hand|in_stock|quantity|balance|remaining|shelf|capacity"
NOT_STOCK = r"price|fee|cost|rate|salary|amount_paid|total"
BLOCK_WORDS = r"\b(refus\w*|reject\w*|not enough|cannot|can't|block\w*|prevent\w*|insufficient|too (?:many|much)|stop\w*)\b"
UP_WORDS = r"\b(go(?:es)? up|increas\w*|rais\w*|add\w* to (?:the|its))\b"
DOWN_WORDS = r"\b(go(?:es)? down|reduc\w*|decreas\w*|lower\w*|subtract\w*|deduct\w*|take\w*\b[^.]{0,30}\b(?:off|away|out|from))\b"


def infer_missing_rule(request, spec):
    """The owner asked for a number to change when a record is added ("the stock must go down, and the sale must be
    refused if there is not enough") but the plan has no rule (core proof A1, 2 GB: the planner left rules empty and the
    build still reported VERIFIED). If exactly one linked pair of records fits, the rule is built from the request's own
    words; otherwise None, and the caller reports it as not built. Returns (rule, note) or (None, reason)."""
    import re
    if spec.get("rules") or not re.search(DOWN_WORDS + "|" + UP_WORDS, request or "", re.I):
        return None, ""
    ents = {e["name"]: e for e in spec.get("entities", [])}
    fits = []
    for child in spec.get("entities", []):
        for lf in links_of(child):
            target = ents.get(lf["to"])
            if not target:
                continue
            amounts = [f for f in child["fields"] if f["type"] == "number" and not re.search(NOT_STOCK, f["name"], re.I)]
            stocks = [f for f in target["fields"] if f["type"] == "number" and not re.search(NOT_STOCK, f["name"], re.I)]
            amounts.sort(key=lambda f: not re.search(AMOUNT_NAMES, f["name"], re.I))
            stocks.sort(key=lambda f: not re.search(STOCK_NAMES, f["name"], re.I))
            if amounts and stocks:
                fits.append((child, lf, target, amounts[0], stocks[0]))
    if len(fits) != 1:
        return None, f"{len(fits)} possible record pairs for the rule the request describes"
    child, lf, target, amount, stock = fits[0]
    up = re.search(UP_WORDS, request, re.I) and not re.search(DOWN_WORDS, request, re.I)
    rule = {"on_add": child["name"], "link_field": lf["name"], "target": target["name"], "target_key": target["search_field"],
            "target_field": stock["name"], "amount_field": amount["name"], "change": "add" if up else "subtract",
            "block_if_negative": bool(not up and re.search(BLOCK_WORDS, request, re.I))}
    return rule, (f"rule added from the request (the plan had none): adding a {child['name']} "
                  f"{'raises' if up else 'lowers'} the {target['name']}'s {stock['name']} by its {amount['name']}"
                  + (", refused if there is not enough" if rule["block_if_negative"] else ""))


def plain_threshold_labels(spec):
    """A dashboard count of records below a threshold must say so ("Medicines in stock" for "fewer than 10 in stock"
    misleads the owner; core proof A1, 2 GB). Labels without a comparison word get one. Returns the notes."""
    import re
    notes = []
    ents = {e["name"]: e for e in spec.get("entities", [])}
    for d in spec.get("dashboard", []):
        if d.get("kind") == "count_below" and not re.search(r"fewer|less|below|under|low|<", d.get("label", ""), re.I):
            e = ents.get(d["entity"], {})
            f = next((x for x in e.get("fields", []) if x["name"] == d.get("field")), {"label": d.get("field", "")})
            what = (f.get("label") or str(f.get("name", "")).replace("_", " ")).lower()
            new = f"{e.get('label', d['entity'])} with fewer than {d['below']:g} {what}".strip()
            notes.append(f"dashboard label '{d['label']}' -> '{new}' (a count below {d['below']:g} must say so)")
            d["label"] = new
    return notes
