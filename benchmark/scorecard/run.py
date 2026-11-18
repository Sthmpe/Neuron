"""Scorecard: four public benchmarks on fixed samples, each frozen model alone and inside NEURON.

  python3 -m benchmark.scorecard.run --tier 2gb --condition alone   [--bench mmlu_pro,gpqa,lcb,bfcl]
  python3 -m benchmark.scorecard.run --tier 2gb --condition neuron

Data lives in $NEURON_BENCH_DATA (default /home/user/bench-data), outside the repository. It is never stored in the
repository (only item ids), never written to NEURON's memory and never used for tuning.

Samples (fixed seed, the same for every model and condition; labelled as samples, not full runs):
  MMLU-Pro (TIGER-Lab, test split)         28 questions, 2 per subject, 10 options
  GPQA Diamond (Idavidrein/gpqa)           20 questions, 4 options shuffled with a fixed seed
  LiveCodeBench code_generation_lite v6    10 AtCoder problems from 2025 (4 easy, 4 medium, 2 hard), judged on
                                           all public and private tests, pass@1
  BFCL v3 (simple + multiple, AST check)   30 items (15 + 15); our re-implementation of the AST check
Conditions:
  alone   one model call per item, the same prompt for every model
  neuron  NEURON's general mechanisms: questions go through neuron.agent.thinking.solve (Python in the sandbox
          when useful, then one checking pass); code is run on the problem's PUBLIC examples in the sandbox and
          repaired up to twice from the failures (private tests stay hidden); function calls use schema-constrained
          output and are validated against the function's parameters, with one retry
Results: benchmark/results/scorecard/<tier>-<condition>.json (resumable: finished items are skipped).
"""
import argparse
import base64
import csv
import json
import math
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmark.run_benchmark import cut_network          # noqa: E402
from neuron.agent.thinking import final_answer, python_block, solve   # noqa: E402
from neuron.brain.models import ModelManager, ModelRunner  # noqa: E402
from neuron.brain.sandbox import Sandbox                  # noqa: E402
from neuron.brain.tiers import Tier                       # noqa: E402

DATA = Path(os.environ.get("NEURON_BENCH_DATA", "/home/user/bench-data"))
SEED = 20261118
LETTERS = "ABCDEFGHIJ"
MB = 2 ** 20


# ---- samples ---------------------------------------------------------------------------------------------
def mmlu_items():
    import pandas as pd
    d = pd.read_parquet(DATA / "mmlu_pro_test.parquet")
    out = []
    for cat in sorted(d["category"].unique()):
        sub = d[d["category"] == cat].sort_values("question_id")
        for i in random.Random(f"{SEED}-{cat}").sample(range(len(sub)), 2):
            r = sub.iloc[i]
            out.append({"id": f"mmlu_pro-{r['question_id']}", "question": r["question"], "options": list(r["options"]),
                        "answer": r["answer"], "subject": cat})
    return out


def gpqa_items():
    rows = list(csv.DictReader(open(DATA / "gpqa_diamond.csv", encoding="utf-8")))
    out = []
    for i in sorted(random.Random(SEED).sample(range(len(rows)), 20)):
        r = rows[i]
        opts = [r["Correct Answer"].strip(), r["Incorrect Answer 1"].strip(), r["Incorrect Answer 2"].strip(), r["Incorrect Answer 3"].strip()]
        order = list(range(4))
        random.Random(f"{SEED}-gpqa-{i}").shuffle(order)
        shuffled = [opts[k] for k in order]
        out.append({"id": f"gpqa-{i}", "question": r["Question"].strip(), "options": shuffled, "answer": LETTERS[order.index(0)]})
    return out


def lcb_items():
    probs = []
    for line in open(DATA / "lcb_test6.jsonl", encoding="utf-8"):
        o = json.loads(line)
        if o["platform"] == "atcoder" and o["contest_date"].startswith("2025"):
            probs.append(o)
    probs.sort(key=lambda o: o["question_id"])
    out = []
    for diff, n in (("easy", 4), ("medium", 4), ("hard", 2)):
        pool = [p for p in probs if p["difficulty"] == diff]
        for p in random.Random(f"{SEED}-lcb-{diff}").sample(pool, n):
            out.append({"id": f"lcb-{p['question_id']}", "statement": p["question_content"], "difficulty": diff,
                        "public": json.loads(p["public_test_cases"]), "private_blob": p["private_test_cases"]})
    return out


def bfcl_items():
    out = []
    for cat in ("simple", "multiple"):
        rows = [json.loads(l) for l in open(DATA / f"bfcl_{cat}.json", encoding="utf-8")]
        answers = {json.loads(l)["id"]: json.loads(l)["ground_truth"] for l in open(DATA / f"bfcl_{cat}_answers.json", encoding="utf-8")}
        for i in sorted(random.Random(f"{SEED}-bfcl-{cat}").sample(range(len(rows)), 15)):
            r = rows[i]
            out.append({"id": f"bfcl-{r['id']}", "functions": r["function"], "request": r["question"][0][-1]["content"],
                        "ground_truth": answers[r["id"]]})
    return out


SAMPLERS = {"mmlu_pro": mmlu_items, "gpqa": gpqa_items, "lcb": lcb_items, "bfcl": bfcl_items}


# ---- multiple choice ---------------------------------------------------------------------------------------
def mc_prompt(item):
    opts = "\n".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(item["options"]))
    return f"{item['question']}\n\nOptions:\n{opts}\n\nChoose the single best option. Finish with: Answer: <letter>"


def letter(text, n):
    valid = LETTERS[:n]
    a = final_answer(text)
    m = re.match(r"\(?([A-J])\)?\b", a.strip())
    if m and m.group(1) in valid:
        return m.group(1)
    hits = re.findall(rf"\b([{valid}])\)", text or "") or re.findall(rf"\b([{valid}])\b", text or "")
    return hits[-1] if hits else ""


def run_mc(item, condition, chat, sandbox):
    q = mc_prompt(item)
    if condition == "alone":
        r = chat([{"role": "system", "content": "Answer the multiple-choice question. Think briefly, then finish with: Answer: <letter>"},
                  {"role": "user", "content": q}], 400)
        got = letter(r.text, len(item["options"]))
        return {"correct": got == item["answer"], "given": got, "calls": 1, "tokens": r.completion_tokens, "tools": {}}
    s = solve(chat, sandbox, q, max_tokens=400)
    got = letter("Answer: " + s["answer"], len(item["options"]))
    return {"correct": got == item["answer"], "given": got, "first_given": letter("Answer: " + s["first_answer"], len(item["options"])),
            "calls": s["calls"], "tokens": s["tokens"], "tools": {"python_runs": s["tool_runs"], "check_pass": 1}}


# ---- code ------------------------------------------------------------------------------------------------
DECODE = r'''
import base64, json, pickle, sys, zlib
blob = open("blob.txt").read()
try:
    data = json.loads(blob)
except ValueError:
    data = json.loads(pickle.loads(zlib.decompress(base64.b64decode(blob.encode("utf-8")))))
json.dump(data, open("tests.json", "w"))
'''


def private_tests(item, sandbox):
    cache = DATA / "lcb_decoded" / f"{item['id']}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    with tempfile.TemporaryDirectory() as d:                 # the dataset packs tests with pickle: decoded only in the sandbox
        Path(d, "blob.txt").write_text(item["private_blob"])
        Path(d, "decode.py").write_text(DECODE)
        r = sandbox.run(["python3", "decode.py"], d, timeout=120)
        if not r.ok:
            raise RuntimeError(f"could not decode private tests: {r.output[-300:]}")
        tests = json.loads(Path(d, "tests.json").read_text())
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(tests))
    return tests


def same_output(got, want):
    g = [l.rstrip() for l in got.strip().splitlines()]
    w = [l.rstrip() for l in want.strip().splitlines()]
    return g == w


def run_tests(code, tests, sandbox, limit=None):
    """Returns (passed, first failure dict or None)."""
    with tempfile.TemporaryDirectory() as d:
        Path(d, "main.py").write_text(code)
        for i, t in enumerate(tests[:limit] if limit else tests):
            Path(d, "input.txt").write_text(t["input"])
            r = sandbox.run(["sh", "-c", "python3 main.py < input.txt"], d, timeout=10)
            if r.timed_out or not same_output(r.output, t["output"]):
                return False, {"input": t["input"][:600], "expected": t["output"][:300], "got": ("TIME LIMIT" if r.timed_out else r.output[:300])}
    return True, None


def run_code(item, condition, chat, sandbox):
    prompt = (f"{item['statement']}\n\nWrite a complete Python 3 program that reads standard input and writes standard output. "
              "Reply with one ```python block.")
    msgs = [{"role": "system", "content": "You write correct, efficient Python 3 programs."}, {"role": "user", "content": prompt}]
    r = chat(msgs, 1200)
    calls, tokens, repairs = 1, r.completion_tokens, 0
    code = python_block(r.text) or ""
    if condition == "neuron":
        for _ in range(2):
            ok, fail = run_tests(code, item["public"], sandbox)
            if ok:
                break
            msgs += [{"role": "assistant", "content": r.text[-3000:]},
                     {"role": "user", "content": f"On this example input:\n{fail['input']}\nthe expected output is:\n{fail['expected']}\n"
                                                 f"but your program printed:\n{fail['got']}\nWrite the corrected complete program in one ```python block."}]
            r = chat(msgs, 1200)
            calls, tokens, repairs = calls + 1, tokens + r.completion_tokens, repairs + 1
            code = python_block(r.text) or code
    tests = item["public"] + private_tests(item, sandbox)
    ok, fail = run_tests(code, tests, sandbox) if code else (False, {"got": "no code"})
    return {"correct": ok, "calls": calls, "tokens": tokens, "tests": len(tests),
            "tools": {"public_example_runs": repairs + (1 if condition == "neuron" else 0), "repairs": repairs} if condition == "neuron" else {}}


# ---- function calling ---------------------------------------------------------------------------------------
def first_json(text):
    start = (text or "").find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += text[i] == "{"
            depth -= text[i] == "}"
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    break
        start = text.find("{", start + 1)
    return None


TYPES = {"integer": int, "float": (int, float), "number": (int, float), "string": str, "boolean": bool, "array": list,
         "tuple": list, "dict": dict, "object": dict}


def validate(call, functions):
    if not isinstance(call, dict) or not isinstance(call.get("arguments"), dict):
        return "the reply is not {\"name\": ..., \"arguments\": {...}}"
    fn = next((f for f in functions if f["name"] == call.get("name")), None)
    if fn is None:
        return f"there is no function named {call.get('name')!r}"
    props = fn["parameters"].get("properties", {})
    missing = [p for p in fn["parameters"].get("required", []) if p not in call["arguments"]]
    if missing:
        return f"missing required parameters: {missing}"
    for k, v in call["arguments"].items():
        if k not in props:
            return f"{k!r} is not a parameter of {fn['name']}"
        t = TYPES.get(props[k].get("type"))
        if t and not isinstance(v, t) or (props[k].get("type") == "integer" and isinstance(v, bool)):
            return f"{k!r} should be of type {props[k].get('type')}"
    return None


def norm(v):
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    return v


def ast_match(call, ground_truth):
    if not isinstance(call, dict) or not isinstance(call.get("arguments"), dict):
        return False
    for gt in ground_truth:
        (name, params), = gt.items()
        if call.get("name") != name:
            continue
        args = call["arguments"]
        if any(k not in params for k in args):
            return False
        ok = True
        for p, allowed in params.items():
            if p in args:
                ok &= any(norm(args[p]) == norm(a) for a in allowed if a != "")
            else:
                ok &= "" in allowed
        if ok:
            return True
    return False


def run_bfcl(item, condition, chat):
    names = [f["name"] for f in item["functions"]]
    prompt = (f"You can call these functions:\n{json.dumps(item['functions'])}\n\nUser request: {item['request']}\n\n"
              "Reply with only one JSON object: {\"name\": <function name>, \"arguments\": {<parameter>: <value>}}.")
    msgs = [{"role": "system", "content": "You turn a request into exactly one function call."}, {"role": "user", "content": prompt}]
    if condition == "alone":
        r = chat(msgs, 300)
        call = first_json(r.text)
        return {"correct": ast_match(call, item["ground_truth"]), "calls": 1, "tokens": r.completion_tokens, "tools": {}}
    schema = {"type": "object", "required": ["name", "arguments"],
              "properties": {"name": {"type": "string", "enum": names}, "arguments": {"type": "object"}}}
    r = chat(msgs, 300, schema)
    calls, tokens, retried = 1, r.completion_tokens, 0
    call = first_json(r.text)
    problem = validate(call, item["functions"])
    if problem:
        msgs += [{"role": "assistant", "content": r.text}, {"role": "user", "content": f"That call is not valid: {problem}. Send the corrected JSON object."}]
        r = chat(msgs, 300, schema)
        calls, tokens, retried = 2, tokens + r.completion_tokens, 1
        call = first_json(r.text) or call
    return {"correct": ast_match(call, item["ground_truth"]), "calls": calls, "tokens": tokens,
            "tools": {"schema_constrained": 1, "validation_retry": retried}}


# ---- main --------------------------------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0, c - h), 3), round(min(1, c + h), 3))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", required=True, choices=["2gb", "4gb", "8gb"])
    ap.add_argument("--condition", required=True, choices=["alone", "neuron"])
    ap.add_argument("--bench", default="mmlu_pro,gpqa,lcb,bfcl")
    a = ap.parse_args(argv)
    out_file = ROOT / "benchmark" / "results" / "scorecard" / f"{a.tier}-{a.condition}.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    res = json.loads(out_file.read_text()) if out_file.exists() else {"rows": [], "summary": {}}
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("The network could not be cut off; refusing to run.")
    tier = Tier(a.tier).enter()
    mgr = ModelManager()
    runner = ModelRunner(mgr, a.tier, log_dir=ROOT / "benchmark" / "run" / "scorecard")
    model = mgr.active(a.tier, "builder")
    res.update(tier=a.tier, condition=a.condition, model=model, model_file=mgr.get(model)["file"], network=net["method"],
               seed=SEED, started=res.get("started") or time.strftime("%Y-%m-%d %H:%M:%S"))
    sandbox = Sandbox(timeout=20, mem_mb=512)
    done = {r["id"] for r in res["rows"]}

    def chat(messages, max_tokens, schema=None):
        return runner.client("builder").chat(messages, max_tokens=max_tokens, temperature=0.0, json_schema=schema)

    try:
        for bench in a.bench.split(","):
            items = SAMPLERS[bench]()
            tier.reset_peak()
            for item in items:
                if item["id"] in done:
                    continue
                t0 = time.time()
                try:
                    if bench in ("mmlu_pro", "gpqa"):
                        row = run_mc(item, a.condition, chat, sandbox)
                    elif bench == "lcb":
                        row = run_code(item, a.condition, chat, sandbox)
                    else:
                        row = run_bfcl(item, a.condition, chat)
                except Exception as e:                       # noqa: BLE001  an item that breaks the harness counts as wrong, and is recorded
                    row = {"correct": False, "error": f"{type(e).__name__}: {str(e)[:200]}", "calls": 0, "tokens": 0, "tools": {}}
                row.update(id=item["id"], bench=bench, seconds=round(time.time() - t0, 1), peak_mb=round(tier.peak_bytes() / MB))
                res["rows"].append(row)
                out_file.write_text(json.dumps(res, indent=1))
                print(f"{a.tier}-{a.condition} {item['id']}: {'right' if row['correct'] else 'wrong'} {row['seconds']}s", flush=True)
            rows = [r for r in res["rows"] if r["bench"] == bench]
            k = sum(r["correct"] for r in rows)
            res["summary"][bench] = {"n": len(rows), "correct": k, "score": round(k / len(rows), 3) if rows else 0, "ci95": wilson(k, len(rows)),
                                     "seconds": round(sum(r["seconds"] for r in rows)), "tokens": sum(r["tokens"] for r in rows),
                                     "calls": sum(r["calls"] for r in rows), "peak_mb": max((r["peak_mb"] for r in rows), default=0)}
            out_file.write_text(json.dumps(res, indent=1))
    finally:
        runner.unload()
        tier.leave()
    print("SCORECARD-DONE", a.tier, a.condition, json.dumps(res["summary"]))


if __name__ == "__main__":
    main()
