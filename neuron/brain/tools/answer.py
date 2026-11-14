"""answer: answer a question with the local language model."""
import hashlib

from ..llm import LLMUnavailable
from .base import Tool, ToolFailure, ToolResult

SYSTEM = ("You are NEURON, a personal AI computer running fully offline on a small local model. "
          "Answer clearly and briefly. If you do not know, say that you do not know.")


class AnswerTool(Tool):
    name = "answer"
    description = ("Answer a question, explain something, or write a short text, using the local language "
                   "model. Works offline. The answer is NOT fact-checked.")
    inputs = {"question": {"type": "string", "description": "The question or request, in full", "required": True}}

    def run(self, ctx):
        llm = ctx.services.get("llm")
        question = str(ctx.params.get("question") or "").strip()
        if not question:
            raise ToolFailure("no question was given")
        if llm is None:
            raise ToolFailure("no local model is configured, so the question was not answered")
        try:
            reply = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
                             max_tokens=700, temperature=0.3)
        except LLMUnavailable as e:
            raise ToolFailure(f"the local model could not be used: {e}") from e
        text = reply.text.strip()
        if not text:
            raise ToolFailure("the local model returned an empty answer", {"llm": reply.stats()})
        evidence = ctx.write(f"answer_step{ctx.step['no']}.txt", text + "\n")
        evidence.update({"llm": reply.stats(), "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
                         "cut_off_by_length_limit": reply.finish_reason == "length"})
        return ToolResult({"answer": text}, f"Answered with the local model {reply.model} "
                          f"({reply.completion_tokens} tokens in {reply.seconds:.1f}s)", evidence,
                          verified=False, verification="model output saved; not fact-checked by anything else")


TOOLS = [AnswerTool()]
