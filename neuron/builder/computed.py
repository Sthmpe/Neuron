"""Computed values in business apps: a total on each record, and sums on the dashboard.

  computed field   {"name": "total", "type": "computed", "formula": "parts + labour"}
                   arithmetic (+ - * / and brackets, numbers) over the record's own number fields, and over a linked
                   record's number field written link.field (for example "quantity * dish.price"). Never stored: worked
                   out in the database query whenever the list is shown, so it is always up to date.
  dashboard sum    {"label": "Total billed", "entity": "repairs", "kind": "sum", "field": "total"}
                   adds up a number or computed field over all records.
Invalid formulas are dropped and recorded (spec["dropped"]), never allowed to break the plan.
"""
import re

from .spec import label, safe_name, slug

TOKEN = re.compile(r"\s*(\d+(?:\.\d+)?|[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?|[-+*/()])")


def _tokens(formula):
    pos, out = 0, []
    formula = str(formula or "")
    while pos < len(formula):
        m = TOKEN.match(formula, pos)
        if not m:
            return None
        out.append(m.group(1))
        pos = m.end()
    return out


def compile_formula(formula, entity, spec):
    """(sql, python_eval_parts) or (None, reason). python parts: list of ("num"|"op", value) or ("field", name) or
    ("link", (link_field, target_entity, target_key, target_field))."""
    toks = _tokens(formula)
    if not toks:
        return None, f"formula {formula!r} has characters I cannot use"
    nums = {f["name"] for f in entity["fields"] if f["type"] == "number"}
    links = {f["name"]: f["to"] for f in entity["fields"] if f["type"] == "link"}
    ents = {e["name"]: e for e in spec["entities"]}
    sql, parts, depth, expect_value = [], [], 0, True
    for t in toks:
        if t in "+-*/":
            if expect_value and t != "-":
                return None, f"formula {formula!r} has an operator in the wrong place"
            sql.append(t), parts.append(("op", t))
            expect_value = True
            continue
        if t == "(":
            depth += 1
            sql.append(t), parts.append(("op", t))
            continue
        if t == ")":
            depth -= 1
            if depth < 0:
                return None, f"formula {formula!r} has unbalanced brackets"
            sql.append(t), parts.append(("op", t))
            expect_value = False
            continue
        if re.match(r"\d", t):
            sql.append(t), parts.append(("num", float(t)))
        elif "." in t:
            lk, tf = (safe_name(slug(x), "value") for x in t.split("."))
            if lk not in links:
                return None, f"{lk!r} in {formula!r} is not a link field of {entity['name']}"
            target = ents[links[lk]]
            if tf not in {f["name"] for f in target["fields"] if f["type"] == "number"}:
                return None, f"{tf!r} in {formula!r} is not a number field of {target['name']}"
            key = target["search_field"]
            sql.append(f"COALESCE((SELECT {tf} FROM {target['name']} WHERE {key} = {entity['name']}.{lk}), 0)")
            parts.append(("link", (lk, target["name"], key, tf)))
        else:
            name = safe_name(slug(t), "value")
            if name not in nums:
                return None, f"{t!r} in {formula!r} is not a number field of {entity['name']}"
            sql.append(f"COALESCE({entity['name']}.{name}, 0)"), parts.append(("field", name))
        expect_value = False
    if depth != 0 or expect_value:
        return None, f"formula {formula!r} is incomplete"
    return " ".join(sql), parts


def evaluate(parts, row, lookup):
    """Work out a compiled formula in Python for an expected value (rows of sample data)."""
    expr = []
    for kind, v in parts:
        if kind in ("op",):
            expr.append(v)
        elif kind == "num":
            expr.append(repr(v))
        elif kind == "field":
            expr.append(repr(float(row.get(v) or 0)))
        else:
            lk, target, key, tf = v
            expr.append(repr(float(lookup(target, key, row.get(lk), tf) or 0)))
    try:
        return eval(" ".join(expr), {"__builtins__": {}}, {})       # only numbers and operators reach here
    except ZeroDivisionError:
        return 0.0


def apply(raw, s, problems):
    """Move computed fields out of the stored fields into entity['computed'], and turn 'sum' dashboard items into sums."""
    ents = {e["name"]: e for e in s.get("entities", [])}
    pending = []
    for re_ in raw.get("entities") if isinstance(raw.get("entities"), list) else []:
        if not isinstance(re_, dict):
            continue
        e = ents.get(safe_name(slug(re_.get("name") or ""), "list"))
        if e is None:
            continue
        e.setdefault("computed", [])
        for rf in re_.get("fields") if isinstance(re_.get("fields"), list) else []:
            if isinstance(rf, dict) and rf.get("type") == "computed":
                name = safe_name(slug(rf.get("name") or ""), "value")
                e["fields"] = [f for f in e["fields"] if f["name"] != name]       # never a stored column
                pending.append((e, name, rf.get("formula")))
    for e, name, formula in pending:          # compile after every entity has its final fields (links included)
        sql, parts = compile_formula(formula, e, s)
        if sql is None:
            s.setdefault("dropped", []).append(f"computed field {e['name']}.{name}: {parts}")
            continue
        e["computed"].append({"name": name, "label": label(name), "formula": str(formula), "sql": sql, "parts": parts})
    for e in ents.values():
        e.setdefault("computed", [])
        if e["search_field"] not in [f["name"] for f in e["fields"]] and e["fields"]:
            e["search_field"] = e["fields"][0]["name"]
    raw_dash = raw.get("dashboard") if isinstance(raw.get("dashboard"), list) else []
    for rd in raw_dash:
        if not isinstance(rd, dict) or rd.get("kind") != "sum":
            continue
        item = next((d for d in s.get("dashboard", []) if d["label"] == str(rd.get("label") or "").strip()), None)
        ent = ents.get(safe_name(slug(rd.get("entity") or ""), "list"))
        field = safe_name(slug(rd.get("field") or ""), "value")
        if ent is None:
            continue
        expr = next((c["sql"] for c in ent["computed"] if c["name"] == field), None)
        if expr is None and field in {f["name"] for f in ent["fields"] if f["type"] == "number"}:
            expr = f"COALESCE({ent['name']}.{field}, 0)"
        if expr is None:
            s.setdefault("dropped", []).append(f"dashboard sum '{rd.get('label')}': {field!r} is not a number or computed field of {ent['name']}")
            if item:
                s["dashboard"].remove(item)
            continue
        new = {"label": str(rd.get("label")).strip(), "entity": ent["name"], "kind": "sum", "field": field, "sql": expr}
        if item:
            s["dashboard"][s["dashboard"].index(item)] = new
        else:
            s["dashboard"].append(new)
    return s


def select_sql(e):
    """SELECT list for an entity's page: every stored column plus each computed value under its own name."""
    extra = "".join(f", ({c['sql']}) AS {c['name']}" for c in e.get("computed", []))
    return f"SELECT *{extra} FROM {e['name']}"


def fmt(value):
    """How the pages show a computed number: the same rule as ui.num in the app kits."""
    v = float(value or 0)
    return str(int(v)) if v.is_integer() else f"{v:.2f}"


def extend_schema(schema):
    """The planner's schema with computed fields and dashboard sums."""
    import copy
    s = copy.deepcopy(schema)
    f = s["properties"]["entities"]["items"]["properties"]["fields"]["items"]
    f["properties"]["type"]["enum"] = list(f["properties"]["type"]["enum"]) + ["computed"]
    f["properties"]["formula"] = {"type": "string"}
    d = s["properties"]["dashboard"]["items"]
    d["properties"]["kind"]["enum"] = list(d["properties"]["kind"]["enum"]) + ["sum"]
    return s
