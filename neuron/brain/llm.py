"""Client for a local llama.cpp server (`llama-server`). Local HTTP only, never through a proxy."""
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class LLMUnavailable(Exception):
    pass


@dataclass
class LLMReply:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    tokens_per_second: float
    finish_reason: str = ""

    def stats(self):
        return {"model": self.model, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "seconds": round(self.seconds, 2),
                "tokens_per_second": round(self.tokens_per_second, 1)}


class LlamaClient:
    def __init__(self, url="http://127.0.0.1:8080", timeout=900):
        self.url, self.timeout = url.rstrip("/"), timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._model = None
        self.calls, self.total_seconds, self.total_completion_tokens = 0, 0.0, 0

    def _req(self, path, body=None, timeout=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data, {"Content-Type": "application/json"})
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise LLMUnavailable(f"local model server error {e.code}: {e.read()[:300]!r}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise LLMUnavailable(f"local model server not reachable at {self.url}: {e}") from e

    def healthy(self):
        try:
            return self._req("/health", timeout=3).get("status") == "ok"
        except LLMUnavailable:
            return False

    def model_name(self):
        if self._model is None:
            try:
                name = self._req("/v1/models", timeout=5)["data"][0]["id"]
                self._model = name.rsplit("/", 1)[-1]
            except (LLMUnavailable, KeyError, IndexError):
                return "unknown"
        return self._model

    def chat(self, messages, max_tokens=1024, temperature=0.2, json_schema=None):
        body = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                "cache_prompt": True}
        if json_schema is not None:
            body["response_format"] = {"type": "json_object", "schema": json_schema}
        start = time.time()
        data = self._req("/v1/chat/completions", body)
        seconds = time.time() - start
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMUnavailable(f"unexpected reply from the local model server: {e}") from e
        usage, timings = data.get("usage") or {}, data.get("timings") or {}
        done = int(usage.get("completion_tokens") or 0)
        self.calls += 1
        self.total_seconds += seconds
        self.total_completion_tokens += done
        return LLMReply(text, self.model_name(), int(usage.get("prompt_tokens") or 0), done, seconds,
                        float(timings.get("predicted_per_second") or (done / seconds if seconds else 0)),
                        choice.get("finish_reason") or "")
