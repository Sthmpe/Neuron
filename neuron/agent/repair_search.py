"""Trying small changes before asking the model: classic automated program repair, no model involved.

Many real bugs are one token wrong: '>' where '>=' was meant, '+' for '-', '*' for '/', an off-by-one number, '&&'
for '||'. For the functions the failing tests point at, every such one-token change is tried in a scratch copy and
the project's own tests are run; the first change that makes ALL of them pass is kept. Nothing is kept otherwise.
This is the same standard as a model's fix (the project's tests decide), it costs no model time, and the change is
exactly one token, so it is easy for a person to review.
"""
import re
import shutil
from pathlib import Path

SWAPS = [("<=", "<"), ("<", "<="), (">=", ">"), (">", ">="), ("==", "!="), ("!=", "=="), ("&&", "||"), ("||", "&&"),
         ("+=", "-="), ("-=", "+="), ("*=", "/="), ("/=", "*="), ("+", "-"), ("-", "+"), ("*", "/"), ("/", "*"),
         ("true", "false"), ("false", "true")]
# an operator token as a whole: never part of '<<', '->', '++', '//', '/*', '<=>' or a template/generic '<T>'
OP = re.compile(r"(?<![<>=!+\-*/&|:])(<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|<|>|\+|-|\*|/)(?![<>=+\-*/&|:])")
WORD = re.compile(r"\b(true|false)\b")
NUM = re.compile(r"(?<![\w.])(\d{1,4})(?![\w.])")


def _code_part(line):
    """The line without its comment or string literals (changes are never made inside them)."""
    out, i, quote = [], 0, None
    while i < len(line):
        c = line[i]
        if quote:
            out.append(" ")
            if c == "\\":
                out.append(" ")
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
            out.append(" ")
        elif line.startswith("//", i) or c == "#":
            break
        else:
            out.append(c)
        i += 1
    return "".join(out)


GENERIC_OPEN = re.compile(r"\s*(?:const\s+)?[A-Za-z_][\w:]*\s*[*&]?\s*(?:,\s*[A-Za-z_][\w:]*\s*[*&]?\s*)*>")
GENERIC_CLOSE = re.compile(r"[A-Za-z_]\w*\s*<\s*(?:const\s+)?[A-Za-z_][\w:]*\s*[*&]?\s*(?:,\s*[A-Za-z_][\w:]*\s*[*&]?\s*)*$")


def _strip_block_comments(lines):
    """Lines with /* ... */ comments blanked out (also across lines), so nothing inside a comment is ever changed."""
    out, inside = [], False
    for line in lines:
        res, i = [], 0
        while i < len(line):
            if inside:
                end = line.find("*/", i)
                if end < 0:
                    res.append(" " * (len(line) - i))
                    i = len(line)
                else:
                    res.append(" " * (end + 2 - i))
                    i, inside = end + 2, False
            else:
                start = line.find("/*", i)
                if start < 0:
                    res.append(line[i:])
                    i = len(line)
                else:
                    res.append(line[i:start])
                    i, inside = start, True
        out.append("".join(res))
    return out


def mutants(text, first, last, limit=140):
    """One-token changes inside lines first..last (1-based). Yields (line number, old line, new line, description)."""
    lines = text.splitlines()
    visible = _strip_block_comments(lines)
    found = []
    for n in range(first, min(last, len(lines)) + 1):
        line = lines[n - 1]
        code = _code_part(visible[n - 1])
        if not code.strip() or code.lstrip().startswith(("#include", "import", "package", "func ", "fn ", "use ")):
            continue
        for m in OP.finditer(code):
            tok = m.group(1)
            if tok == "<" and GENERIC_OPEN.match(code[m.end():]) and re.search(r"[A-Za-z_]\w*\s*$", code[:m.start()]):
                continue                                # vector<int>, map<string, int>: a type, not a comparison
            if tok == ">" and GENERIC_CLOSE.search(code[:m.start()]):
                continue                                # the end of such a type
            # (x<5 is a comparison: Astra's review of main d54bf4d found it skipped because of the old \w< test)
            before = code[:m.start()]
            if tok in ("*", "-", "+") and (not re.search(r"[\w)\]]\s*$", before) or re.search(r"\b(return|case|else|in|throw)\s*$", before)):
                continue                                # a sign or a dereference, not arithmetic
            for old, new in SWAPS:
                if old == tok:
                    found.append((n, line, line[:m.start()] + new + line[m.end():], f"'{old}' -> '{new}'"))
        for m in WORD.finditer(code):
            new = "false" if m.group(1) == "true" else "true"
            found.append((n, line, line[:m.start()] + new + line[m.end():], f"'{m.group(1)}' -> '{new}'"))
        for m in NUM.finditer(code):
            v = int(m.group(1))
            for nv in (v + 1, v - 1):
                if nv >= 0:
                    found.append((n, line, line[:m.start()] + str(nv) + line[m.end():], f"{v} -> {nv}"))
        found += _wider_mutants(n, line, code, lines, first, last)
    # comparisons and arithmetic first (the commonest one-token bugs), then numbers, then the wider changes
    order = {"'<": 0, "'>": 0, "'=": 0, "'!": 0, "'&": 1, "'|": 1, "'+": 2, "'-": 2, "'*": 2, "'/": 2, "'t": 3, "'f": 3}
    found.sort(key=lambda x: WIDER.get(x[3].split(":")[0], order.get(x[3][:2], 4)))
    return found[:limit]


# Wider standard repair operators (added after the core proof's 2 GB run 1, where NEURON fixed 0 of 8 planted bugs:
# a rate written 0.75 for 7.5 percent, a stray '/ 100', text[0] for the first two characters, a fee charged twice).
# Each is generic: scale or nudge a constant, drop a constant operand, widen an index to a slice, delete one statement.
DEC = re.compile(r"(?<![\w.])(\d+\.\d+)(?![\w.])")
DROP = re.compile(r"\s*[*/]\s*\d+(?:\.\d+)?(?![\w.])")
INDEX = re.compile(r"(?<=[\w)\]])\[(\d)\]")
PERCENT = re.compile(r"\*\s*[A-Za-z_.]*(?:percent|pct|percentage)\w*(?!\s*/)", re.I)
WIDER = {"drop": 5, "scale": 6, "slice": 7, "delete": 8}


def _num(v):
    return f"{v:.6f}".rstrip("0").rstrip(".") if v != int(v) else (str(int(v)) + (".0" if False else ""))


def _wider_mutants(n, line, code, lines, first, last):
    out = []
    for m in DROP.finditer(code):
        out.append((n, line, line[:m.start()] + line[m.end():], f"drop: removed '{m.group(0).strip()}'"))
    for m in DEC.finditer(code):
        v = float(m.group(1))
        for nv in (v * 10, v / 10, v * 2, v / 2, v + 0.25, v - 0.25, v + 0.5, v - 0.5):
            if nv > 0 and abs(nv - v) > 1e-12:
                txt = _num(nv) if "." in _num(nv) else _num(nv) + ".0"
                out.append((n, line, line[:m.start()] + txt + line[m.end():], f"scale: {m.group(1)} -> {txt}"))
    for m in NUM.finditer(code):
        v = int(m.group(1))
        for nv in ((v * 10, v // 10) if v % 10 == 0 and v else (v * 10,)):
            if nv > 0:
                out.append((n, line, line[:m.start()] + str(nv) + line[m.end():], f"scale: {v} -> {nv}"))
    for m in PERCENT.finditer(code):          # a percentage used as a fraction: x * percent -> x * percent / 100
        out.append((n, line, line[:m.end()] + " / 100" + line[m.end():], f"drop: added '/ 100' after '{m.group(0).strip()}'"))
    for m in INDEX.finditer(code):
        k = int(m.group(1))
        for sl in (f"[:{k + 1}]", f"[:{k + 2}]", f"[{k}:]"):
            out.append((n, line, line[:m.start()] + sl + line[m.end():], f"slice: [{k}] -> {sl}"))
    stripped = code.strip()
    if n > first and n < last and stripped and not re.match(r"(return|def|func|fn|if|for|while|else|elif|switch|case|try|"
                                                            r"catch|except|class|struct|let|const|var|import|package)\b", stripped) \
            and not stripped.endswith(("{", "}", ":", ",", "(", "[")) and (re.search(r"[+\-*/]?=(?!=)", stripped) or stripped.endswith(";")):
        indent = line[:len(line) - len(line.lstrip())]
        repl = indent + "pass" if line.rstrip().endswith(tuple("abcdefghijklmnopqrstuvwxyz0123456789)]'\"")) and not stripped.endswith(";") else ""
        out.append((n, line, repl, f"delete: removed line {n}"))
    return out


def _equivalent_form(lines):
    """A form in which two changes that mean the same thing look the same, so they do not count as two different fixes:
    deleting either of two identical lines; 'x > 64' and 'x >= 65' (and '<= 64' / '< 65') with whole numbers; spacing."""
    text = "\n".join(l.strip() for l in lines if l.strip() and l.strip() != "pass")
    text = re.sub(r"(?<![-<>=!])>(?!=)\s*(\d+)(?![\d.])", lambda m: ">=" + str(int(m.group(1)) + 1), text)
    text = re.sub(r"(?<![<>=!])<=\s*(\d+)(?![\d.])", lambda m: "<" + str(int(m.group(1)) + 1), text)
    return re.sub(r"\s+", "", text)


def search(workspace, suspects, test_cmd, sandbox, passed_fn, max_tries=90, log=print, look_further=25):
    """suspects: [(file, name, first line, last line)], most likely first. Returns a dict describing the fix, a dict
    {"ambiguous": [fixes]} when several different changes pass, or None. The workspace is changed only for a single
    unambiguous fix.

    A change can pass the project's tests and still be wrong (after-fixes rerun try 1, B3 on 2 GB: text[0] -> text[1]
    passed the tests, which use hours like 08 and 13, but is wrong for "12:45"). So after the first passing change the
    search looks further (up to `look_further` more tries); if a different change also passes, the caller must choose
    (the model picks among them) instead of trusting the first."""
    ws = Path(workspace)
    scratch = ws.parent / (ws.name + "__repair")
    shutil.rmtree(scratch, ignore_errors=True)
    shutil.copytree(ws, scratch, ignore=shutil.ignore_patterns(".neuron", "__pycache__", ".git", "*.o"))
    tries, first, wins, seen = 0, None, [], set()
    try:
        for f, name, a, b in suspects:
            original = (ws / f).read_text()
            for n, old, new, desc in mutants(original, a, b):
                if tries >= max_tries or (first is not None and tries - first >= look_further):
                    break
                tries += 1
                lines = original.splitlines()
                lines[n - 1] = new
                text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
                same = _equivalent_form(lines)
                if (f, same) in seen:
                    continue
                (scratch / f).write_text(text)
                res = sandbox.run(test_cmd, scratch, timeout=120)
                if passed_fn(res):
                    seen.add((f, same))
                    wins.append({"file": f, "function": name, "line": n, "old": old.strip(), "new": new.strip(), "change": desc,
                                 "tries": tries, "text": text})
                    first = tries if first is None else first
                    log(f"    small change passes the tests after {tries} tries: {f}:{n} {desc}")
            (scratch / f).write_text(original)
        if not wins:
            return None
        if len(wins) > 1:
            return {"ambiguous": wins, "tries": tries}
        win = wins[0]
        (ws / win["file"]).write_text(win.pop("text"))
        return win
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def choose(job, wins, source_of):
    """Several different small changes pass the tests: the model picks the one that is right for all inputs, or none.
    Returns the chosen fix (applied to the workspace) or None."""
    opts = [f"{w['file']} line {w['line']}: {w['old']}  ->  {w['new']}" for w in wins]
    data = job.ask_json("reviewer", "Several small changes make a project's tests pass, but only a correct one works for all "
                        "inputs, not just the tested ones. Pick the correct change, judged by what the code is meant to do.",
                        "Code:\n" + "\n\n".join(dict.fromkeys(source_of(w) for w in wins)) + "\n\nCandidate changes:\n"
                        + "\n".join(f"- {o}" for o in opts),
                        {"type": "object", "required": ["change", "why"],
                         "properties": {"change": {"type": "string", "enum": opts}, "why": {"type": "string"}}}, max_tokens=400)
    if not data or data.get("change") not in opts:
        return None
    win = dict(wins[opts.index(data["change"])])
    (Path(job.workspace) / win["file"]).write_text(win.pop("text"))
    job.state.decide("fix", "small change chosen", f"{len(wins)} different small changes passed the tests; the model chose "
                     f"{data['change']} ({str(data.get('why', ''))[:160]})")
    win["change"] += f" (chosen by the model from {len(wins)} changes that pass the tests)"
    return win
