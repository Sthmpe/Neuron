"""Outside actions done at most once, even if NEURON stops in the middle of one.

Every action that changes something beyond the job's own scratch work (fetching photos into a delivered project,
swapping upgraded packages into it, later: sending a message or paying) goes through Effects.once(key, what, fn):

  1. a 'started' line is written to .neuron/job/effects.jsonl and flushed to disk before the action,
  2. the action runs,
  3. a 'done' line with its result is written after it.

On any later run of the same job:
  done      the stored result is returned and the action is NOT repeated (counted as a blocked duplicate).
  started   NEURON stopped in the middle, so nobody knows whether the action happened.
            repeat_safe actions (writing a file that is checked afterwards) simply run again;
            anything else raises Uncertain and the job asks the owner before doing it again.
The key must name the action and its target (for example "images:hero" or "upgrade:requirements.txt:flask==3.1.0"),
so the same action on the same thing is recognised across restarts.
"""
import json
import os
import time
from pathlib import Path


class Uncertain(Exception):
    """An outside action was started but never recorded as finished. Only the owner can say whether it happened."""

    def __init__(self, key, what):
        super().__init__(f"stopped in the middle of: {what}")
        self.key, self.what = key, what


class Effects:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.replayed = 0                 # duplicates blocked in this session

    def _lines(self):
        """Every readable record. A damaged line (a crash in the middle of a write) is skipped, never the whole history:
        losing the record that an action already ran could make it run twice (Astra's review of 1f65640)."""
        try:
            text = self.path.read_text(errors="replace")
        except OSError:
            return []
        out = []
        for x in text.splitlines():
            if x.strip():
                try:
                    out.append(json.loads(x))
                except ValueError:
                    continue
        return out

    def _append(self, rec):
        with open(self.path, "a") as f:
            f.write(json.dumps({"at": time.time(), **rec}) + "\n")
            f.flush()
            os.fsync(f.fileno())          # on disk before the action starts / before we report it done

    def state(self, key):
        """(status, last record) for a key: (None, None), ('started', rec), ('done', rec) or ('cancelled', rec)."""
        last = None
        for rec in self._lines():
            if rec.get("key") == key:
                last = rec
        return (last["status"], last) if last else (None, None)

    def once(self, key, what, fn, repeat_safe=False):
        status, rec = self.state(key)
        if status == "done":
            self.replayed += 1
            self._append({"key": key, "status": "done", "what": what, "result": rec.get("result"), "replay": True})
            return rec.get("result")
        if status == "started" and not repeat_safe:
            raise Uncertain(key, what)
        self._append({"key": key, "status": "started", "what": what})
        result = fn()
        self._append({"key": key, "status": "done", "what": what, "result": result})
        return result

    def resolve(self, key, happened, result=None):
        """The owner's answer about an interrupted action: it happened (never repeat it) or it did not (may run again)."""
        status, rec = self.state(key)
        if status != "started":
            return
        what = rec.get("what", "")
        if happened:
            self._append({"key": key, "status": "done", "what": what, "result": result, "by_owner": True})
        else:
            self._append({"key": key, "status": "cancelled", "what": what, "by_owner": True})

    def unfinished(self):
        latest = {}
        for rec in self._lines():
            latest[rec["key"]] = rec
        return [r for r in latest.values() if r["status"] == "started"]

    def summary(self):
        lines = self._lines()
        latest = {}
        for rec in lines:
            latest[rec["key"]] = rec
        return {"outside_actions": sum(1 for r in latest.values() if r["status"] == "done"),
                "duplicates_blocked": sum(1 for r in lines if r.get("replay")),
                "unfinished": [r["what"] for r in latest.values() if r["status"] == "started"]}
