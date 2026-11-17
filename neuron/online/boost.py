"""Optional online boost. OFF unless the owner turns it on. NEURON never needs it to work.

When it is on, and the internet is up, chosen roles (for example the planner and the reviewer)
ask an online model that speaks the common chat-completions format. Anything going wrong
(no internet, timeout, error, spending cap reached) means that call goes to the local model
instead, and the boost rests for a few minutes. Every answer says where it came from, so a job
report can say how many calls went online.

Turning it on means: the prompts for those roles, which can contain parts of your files, are
sent to that provider. That is why it is off by default and needs a settings file written by
the owner: <NEURON home>/online.json, readable only by the owner, for example

  {"enabled": true, "provider": "my provider", "base_url": "https://api.example.com/v1",
   "model": "model-name", "api_key_env": "MY_PROVIDER_KEY", "roles": ["planner", "reviewer"],
   "timeout_s": 60, "max_calls_per_job": 60}

The key is read from the named environment variable (or "api_key" in the file). It is never
written to logs or job files.
"""
import json
import os
import stat
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..brain.llm import LLMReply

REST_SECONDS = 180


class OnlineBoost:
    def __init__(self, cfg, online_check=None, log=print):
        self.cfg, self.log = dict(cfg or {}), log
        self.online_check = online_check or (lambda: True)
        self.calls = self.failures = self.job_calls = 0
        self.resting_until = 0.0
        self.last_problem = ""

    @classmethod
    def from_home(cls, home, online_check=None, log=print):
        f = Path(home) / "online.json"
        if not f.exists():
            return cls({}, online_check, log)
        if f.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):
            log("online boost: online.json is readable by other users; fix with chmod 600. Boost stays off.")
            return cls({}, online_check, log)
        return cls(json.loads(f.read_text()), online_check, log)

    def key(self):
        return self.cfg.get("api_key") or os.environ.get(self.cfg.get("api_key_env") or "", "")

    def configured(self):
        return bool(self.cfg.get("enabled") and self.cfg.get("base_url") and self.cfg.get("model") and self.key())

    def wants(self, role):
        return self.configured() and role in (self.cfg.get("roles") or [])

    def usable(self, role):
        if not self.wants(role) or time.time() < self.resting_until:
            return False
        if self.job_calls >= int(self.cfg.get("max_calls_per_job", 60)):
            return False
        return bool(self.online_check())

    def new_job(self):
        self.job_calls = 0

    def status(self):
        if not self.configured():
            return {"on": False, "why": "not turned on" if not self.cfg.get("enabled") else "settings incomplete (address, model or key)"}
        return {"on": True, "provider": self.cfg.get("provider") or self.cfg["base_url"], "model": self.cfg["model"],
                "roles": self.cfg.get("roles") or [], "calls": self.calls, "failures": self.failures,
                "resting": time.time() < self.resting_until, "last_problem": self.last_problem}

    def chat(self, messages, max_tokens=1024, temperature=0.2, json_schema=None):
        body = {"model": self.cfg["model"], "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if json_schema is not None:
            body["response_format"] = {"type": "json_object"}
            messages = list(messages)
            messages[-1] = dict(messages[-1], content=messages[-1]["content"] + "\n\nReply with JSON only, matching this schema:\n"
                                + json.dumps(json_schema))
            body["messages"] = messages
        req = urllib.request.Request(self.cfg["base_url"].rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key()})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=float(self.cfg.get("timeout_s", 60))) as r:
            data = json.loads(r.read())
        seconds = time.time() - t0
        choice = data["choices"][0]
        usage = data.get("usage") or {}
        done = int(usage.get("completion_tokens") or 0)
        self.calls += 1
        self.job_calls += 1
        return LLMReply(choice["message"].get("content") or "", f"online:{self.cfg.get('provider') or 'boost'}/{self.cfg['model']}",
                        int(usage.get("prompt_tokens") or 0), done, seconds, done / seconds if seconds else 0.0,
                        choice.get("finish_reason") or "")

    def failed(self, err):
        self.failures += 1
        self.resting_until = time.time() + REST_SECONDS
        text = str(err).replace(self.key(), "***") if self.key() else str(err)
        self.last_problem = f"{type(err).__name__}: {text}"[:200]
        self.log(f"online boost failed ({self.last_problem}); using the local model, boost rests {REST_SECONDS} s")


class _Client:
    def __init__(self, runner, role):
        self.runner, self.role = runner, role

    def chat(self, messages, **kw):
        boost = self.runner.boost
        if boost.usable(self.role):
            try:
                return boost.chat(messages, **kw)
            except (urllib.error.URLError, OSError, TimeoutError, ValueError, KeyError, IndexError) as e:
                boost.failed(e)
        return self.runner.local.client(self.role).chat(messages, **kw)


class BoostedRunner:
    """Same interface as ModelRunner. The local model stays the default and the fallback."""

    def __init__(self, local, boost):
        self.local, self.boost = local, boost

    @property
    def loaded(self):
        return self.local.loaded

    @property
    def loads(self):
        return getattr(self.local, "loads", 0)

    def model_for(self, role):
        local = self.local.model_for(role)
        return f"{local} (online boost: {self.boost.cfg['model']} when reachable)" if self.boost.wants(role) else local

    def client(self, role):
        return _Client(self, role)

    def unload(self):
        self.local.unload()
