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


def mutants(text, first, last, limit=80):
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
    # comparisons and arithmetic first (the commonest one-token bugs), numbers last
    order = {"'<": 0, "'>": 0, "'=": 0, "'!": 0, "'&": 1, "'|": 1, "'+": 2, "'-": 2, "'*": 2, "'/": 2, "'t": 3, "'f": 3}
    found.sort(key=lambda x: order.get(x[3][:2], 4))
    return found[:limit]


def search(workspace, suspects, test_cmd, sandbox, passed_fn, max_tries=60, log=print):
    """suspects: [(file, name, first line, last line)], most likely first. Returns a dict describing the fix, or None.
    The workspace is changed only when a change made every test pass."""
    ws = Path(workspace)
    scratch = ws.parent / (ws.name + "__repair")
    shutil.rmtree(scratch, ignore_errors=True)
    shutil.copytree(ws, scratch, ignore=shutil.ignore_patterns(".neuron", "__pycache__", ".git", "*.o"))
    tries = 0
    try:
        for f, name, a, b in suspects:
            original = (ws / f).read_text()
            for n, old, new, desc in mutants(original, a, b):
                if tries >= max_tries:
                    return None
                tries += 1
                lines = original.splitlines()
                lines[n - 1] = new
                (scratch / f).write_text("\n".join(lines) + ("\n" if original.endswith("\n") else ""))
                res = sandbox.run(test_cmd, scratch, timeout=120)
                if passed_fn(res):
                    (ws / f).write_text((scratch / f).read_text())
                    log(f"    small change fixed it after {tries} tries: {f}:{n} {desc}")
                    return {"file": f, "function": name, "line": n, "old": old.strip(), "new": new.strip(), "change": desc,
                            "tries": tries}
            (scratch / f).write_text(original)
        return None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
