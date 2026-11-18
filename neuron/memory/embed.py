"""Turning text into vectors for meaning-based search.

LlamaEmbedder runs the small bge-small-en-v1.5 model (37 MB, 384 dimensions) with llama.cpp in embedding mode, beside the
reasoning model (it fits the 2 GB tier: about 60 MB in memory). HashEmbedder is the fallback when that model or llama.cpp
is missing: character 3-grams hashed into 512 dimensions, which catches spelling variants and shared word parts but not
real meaning. The embedder's name is stored with every vector, so vectors from different embedders are never compared.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _normalise(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HashEmbedder:
    name = "hash-3gram-512"
    min_similarity = 0.25

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * 512
            s = " " + re.sub(r"\s+", " ", (t or "").lower()) + " "
            for i in range(len(s) - 2):
                h = int(hashlib.md5(s[i:i + 3].encode()).hexdigest()[:8], 16)
                v[h % 512] += 1.0 if (h >> 9) & 1 else -1.0
            out.append(_normalise(v))
        return out


class LlamaEmbedder:
    name = "bge-small-en-v1.5-q8"
    min_similarity = 0.55

    def __init__(self, model_file, binary=None):
        from ..brain.llama_server import DEFAULT_BIN, LlamaServer
        man = json.loads((REPO / "model_manifests" / "bge-small-en-v1.5-q8.json").read_text())
        self.server = LlamaServer(model_file, binary=binary or DEFAULT_BIN, port=18190, ctx=man["context_tokens"],
                                  threads=2, extra_args=man["server_args"])
        self.started = False

    def _start(self):
        if not self.started:
            self.server.start(wait=120)
            self.started = True

    def embed(self, texts):
        self._start()
        body = json.dumps({"input": [t[:1500] for t in texts]}).encode()
        req = urllib.request.Request(self.server.url + "/v1/embeddings", data=body, headers={"Content-Type": "application/json"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        data = json.loads(opener.open(req, timeout=120).read())
        return [_normalise(d["embedding"]) for d in sorted(data["data"], key=lambda d: d["index"])]

    def close(self):
        if self.started:
            self.server.stop()
            self.started = False


_SHARED = {}


def _close_shared():
    e = _SHARED.pop("llama", None)
    if e is not None:
        e.close()


def best_embedder():
    """The embedding model if it is installed and llama.cpp can run it; otherwise the fallback. One embedding server per
    process, shared by every memory store, stopped when the process exits (a measurement run left several running)."""
    if os.environ.get("NEURON_EMBEDDER") == "hash":
        return HashEmbedder()
    if "llama" in _SHARED:
        return _SHARED["llama"]
    model_dir = Path(os.environ.get("NEURON_MODEL_DIR", str(REPO / "models")))
    f = model_dir / "store" / "bge-small-en-v1.5-q8_0.gguf"
    try:
        from ..brain.llama_server import DEFAULT_BIN
        if f.exists() and Path(DEFAULT_BIN).exists():
            e = LlamaEmbedder(f)
            e.embed(["test"])
            import atexit
            _SHARED["llama"] = e
            atexit.register(_close_shared)
            return e
    except Exception:                       # noqa: BLE001  any problem: fall back, never break the job
        pass
    return HashEmbedder()
