"""Pairing and device tokens. A 6-digit code is shown on the NEURON machine; the phone exchanges it once
for a long random token. Only token holders can use the API. Tokens are stored hashed."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

CODE_TTL = 600            # seconds a pairing code stays valid
MAX_TRIES = 5             # wrong codes allowed per window before pairing locks for the window


class Pairing:
    def __init__(self, home):
        self.file = Path(home) / "devices.json"
        self.lock = threading.Lock()
        self.code, self.code_at, self.fails, self.fail_window = None, 0.0, 0, 0.0
        self.data = json.loads(self.file.read_text()) if self.file.exists() else {"salt": secrets.token_hex(16), "devices": []}
        self._save()

    def _save(self):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.file)

    def _hash(self, token):
        return hashlib.sha256((self.data["salt"] + token).encode()).hexdigest()

    def new_code(self):
        with self.lock:
            self.code, self.code_at = f"{secrets.randbelow(10 ** 6):06d}", time.time()
            return self.code

    def pair(self, code, name="phone"):
        """Returns a new device token, or None. Codes are single-use and expire."""
        with self.lock:
            now = time.time()
            if now - self.fail_window > CODE_TTL:
                self.fails, self.fail_window = 0, now
            if self.fails >= MAX_TRIES:
                return None
            if not self.code or now - self.code_at > CODE_TTL or not hmac.compare_digest(str(code).strip(), self.code):
                self.fails += 1
                return None
            self.code = None
            token = secrets.token_urlsafe(32)
            self.data["devices"].append({"name": str(name)[:40], "hash": self._hash(token), "paired_at": now})
            self._save()
            return token

    def check(self, token):
        if not token:
            return None
        h = self._hash(token)
        for d in self.data["devices"]:
            if hmac.compare_digest(d["hash"], h):
                return d
        return None

    def forget_all(self):
        with self.lock:
            self.data["devices"] = []
            self._save()
