"""Test doubles. These stand in for the local model ONLY inside unit tests, so the logic
around the model (validation, retries, fallback, proof) can be tested quickly and exactly.
They are never used by the brain, the demo or the benchmark."""
from neuron.brain.llm import LLMReply, LLMUnavailable


class ScriptedLLM:
    """Replies with a prepared list of answers, in order. An Exception in the list is raised."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def healthy(self):
        return True

    def model_name(self):
        return "scripted-test-double"

    def chat(self, messages, max_tokens=1024, temperature=0.2, json_schema=None):
        self.calls.append({"messages": messages, "json_schema": json_schema})
        if not self.replies:
            raise LLMUnavailable("scripted test double has no more replies")
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(messages)
        if isinstance(reply, BaseException):
            raise reply
        return LLMReply(reply, self.model_name(), 100, 50, 0.01, 5000.0, "stop")
