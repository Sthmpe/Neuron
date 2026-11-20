"""General problem solving used by NEURON for questions: think, compute with real Python in the sandbox when a
calculation helps, then check the answer once. Nothing here knows about any benchmark."""
import re
import tempfile
from pathlib import Path

SOLVE_SYSTEM = ("You solve problems carefully and briefly. If a calculation or a check by code would help, write one short "
                "Python program in a ```python block that prints the complete final answer to stdout. Use stderr for diagnostics. "
                "Finish with a final line exactly like: Answer: <your answer>")
CHECK_SYSTEM = ("You check a proposed solution. Look for mistakes in reasoning and arithmetic. If it is right, keep the answer; "
                "if it is wrong, correct it. Be brief. Finish with a final line exactly like: Answer: <your answer>")


def final_answer(text):
    m = re.findall(r"answer\s*[:\-]\s*\**\s*(.+)", text or "", re.I)
    return m[-1].strip().strip("*").strip() if m else ""


def python_block(text):
    m = re.search(r"```python\s*\n(.*?)```", text or "", re.S)
    return m.group(1) if m else None


def solve(chat, sandbox, question, max_tool_rounds=2, max_tokens=400):
    """A successful program owns the result. A review can revise a model-only answer."""
    msgs = [{"role": "system", "content": SOLVE_SYSTEM}, {"role": "user", "content": question}]
    calls = tokens = tool_runs = 0
    reply = ""
    computed = None
    for rnd in range(max_tool_rounds + 1):
        r = chat(msgs, max_tokens)
        calls, tokens, reply = calls + 1, tokens + r.completion_tokens, r.text
        code = python_block(reply)
        if not code or rnd == max_tool_rounds or sandbox is None:
            break
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "calc.py").write_text(code)
            out = sandbox.run(["python3", "calc.py"], directory, timeout=20, capture_stdout=True)
        tool_runs += 1
        if out.ok and out.stdout and out.stdout.strip():
            computed = out.stdout.rstrip("\r\n")
            break
        msgs.extend([{"role": "assistant", "content": reply}, {"role": "user", "content":
            f"The program did not produce a complete successful result. Diagnostics:\n{out.output[:1500]}\n"
            "Correct the program and print the final answer."}])

    first = final_answer(reply)
    review = ""
    if computed is not None or not tool_runs:
        evidence = f"\n\nOutput of your program:\n{computed[:1500]}" if computed is not None else ""
        try:
            chk = chat([{"role": "system", "content": CHECK_SYSTEM}, {"role": "user", "content":
                        f"Problem:\n{question}\n\nProposed solution:\n{reply[-2500:]}{evidence}\n\nCheck it."}], max_tokens)
            calls, tokens = calls + 1, tokens + chk.completion_tokens
            review = final_answer(chk.text)
        except Exception:
            # A failed advisory review must not discard a successful execution.
            if computed is None:
                raise
    if computed is not None:
        answer = computed
    elif tool_runs:
        answer = ""
    else:
        answer = review or first
    return {"answer": answer, "first_answer": first or computed or "", "tool_runs": tool_runs, "calls": calls, "tokens": tokens,
            "computed": computed is not None, "review_answer": review}
