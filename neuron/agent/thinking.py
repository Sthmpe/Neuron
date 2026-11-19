"""General problem solving used by NEURON for questions: think, compute with real Python in the sandbox when a
calculation helps, then check the answer once. Nothing here knows about any benchmark."""
import re
import tempfile

SOLVE_SYSTEM = ("You solve problems carefully and briefly. If a calculation or a check by code would help, write one short "
                "Python program in a ```python block that prints what you need; you will be shown its output. "
                "Finish with a final line exactly like: Answer: <your answer>")
CHECK_SYSTEM = ("You check a proposed solution. Look for mistakes in reasoning and arithmetic. If it is right, keep the answer; "
                "if it is wrong, correct it. Be brief. Finish with a final line exactly like: Answer: <your answer>")


def final_answer(text):
    m = re.findall(r"answer\s*[:\-]\s*\**\s*(.+)", text or "", re.I)
    return m[-1].strip().strip("*").strip() if m else ""


def python_block(text):
    m = re.search(r"```python\s*\n(.*?)```", text or "", re.S)
    return m.group(1) if m else None


CODE_ASK = ("Write one short Python program that computes the answer and prints it. Reply with one ```python block only.")


def solve(chat, sandbox, question, max_tool_rounds=2, max_tokens=400, require_code=False):
    """chat(messages, max_tokens) -> LLMReply. Returns {"answer", "first_answer", "tool_runs", "calls", "tokens", "printed"}.
    require_code: the arithmetic is always done by a real program in the sandbox, never in the model's head (small models
    get sums wrong: the 2 GB model answered 44 for an average of 45 without running anything). The scorecard used the
    default (False), so its measurements are unchanged."""
    msgs = [{"role": "system", "content": SOLVE_SYSTEM}, {"role": "user", "content": question}]
    calls = tokens = tool_runs = 0
    reply, printed = "", ""
    for rnd in range(max_tool_rounds + 1):
        r = chat(msgs, max_tokens)
        calls, tokens, reply = calls + 1, tokens + r.completion_tokens, r.text
        code = python_block(reply)
        if require_code and not code and tool_runs == 0 and rnd < max_tool_rounds and sandbox is not None:
            msgs += [{"role": "assistant", "content": reply}, {"role": "user", "content": CODE_ASK}]
            continue
        if code and (not final_answer(reply) or (require_code and tool_runs == 0)) and rnd < max_tool_rounds and sandbox is not None:
            with tempfile.TemporaryDirectory() as d:
                (__import__("pathlib").Path(d) / "calc.py").write_text(code)
                out = sandbox.run(["python3", "calc.py"], d, timeout=20)
            tool_runs += 1
            printed = out.output.strip()[:1500] if out.ok else ""
            msgs += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": f"Output of your program:\n{out.output.strip()[:1500] or '(nothing printed)'}\n"
                                                 "Continue, and finish with: Answer: <your answer>"}]
            continue
        break
    first = final_answer(reply)
    chk = chat([{"role": "system", "content": CHECK_SYSTEM},
                {"role": "user", "content": f"Problem:\n{question}\n\nProposed solution:\n{reply[-2500:]}\n\nCheck it."}], max_tokens)
    calls, tokens = calls + 1, tokens + chk.completion_tokens
    final = final_answer(chk.text) or first
    if require_code and not final and printed and len(printed.splitlines()) == 1:     # the printed result is the answer
        final = printed
    return {"answer": final, "first_answer": first, "tool_runs": tool_runs, "calls": calls, "tokens": tokens, "printed": printed}
