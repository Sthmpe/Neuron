"""Phase 2: freeze one reasoning model per tier, from benchmark/results/selection.json.

Writes model_manifests/frozen.json with, for each tier: model id, file, SHA-256 (from the verified
download record), source address, size, licence, the exact llama.cpp settings, measured memory and
the selection score. The installer reads only this file. Changing it later is a new freeze, recorded
in PROGRESS.md, never a quiet edit."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LLAMA = {"source": "llama.cpp as vendored in llama-cpp-python 0.3.36 (PyPI sdist)", "build": "CPU only, GGML_NATIVE=ON, static",
         "server_flags": ["--load-mode", "none", "--cache-ram", "0"]}


def main():
    sel = json.loads((ROOT / "benchmark" / "results" / "selection.json").read_text())
    sums = {}
    for line in (ROOT / "models" / "store" / "SHA256SUMS").read_text().splitlines():
        sha, name, repo = line.split()
        sums[name] = (sha, repo)
    state = json.loads((ROOT / "models" / "state.json").read_text())["installed"]
    tiers = {}
    for tier, s in sel.items():
        mid = s["winner"]
        if not mid:
            raise SystemExit(f"tier {tier} has no winner; nothing frozen")
        man = json.loads((ROOT / "model_manifests" / f"{mid}.json").read_text())
        sha, repo = sums[man["file"]]
        row = next(r for r in s["candidates"] if r["model"] == mid)
        res = json.loads((ROOT / "benchmark" / "results" / "dev" / f"{tier}-full-sel-{mid}.json").read_text())["rows"]
        peak = max((r.get("peak_mb") or 0) for r in res)
        size = (ROOT / "models" / "store" / man["file"]).stat().st_size
        tiers[tier] = {"id": mid, "file": man["file"], "sha256": sha, "source": man["source"], "repo": repo, "bytes": size,
                       "licence": man.get("licence"), "params_billion": man.get("params_billion"),
                       "context_tokens": man.get("context_tokens", 8192), "server_args": man.get("server_args") or [],
                       "request_extra": man.get("request_extra") or {},
                       "measured_rss_mb": round((state.get(mid, {}).get("measured_rss_bytes") or 0) / 2 ** 20) or None,
                       "peak_tier_memory_mb_in_selection": peak or None,
                       "selection": {"score": row["score"], "of": row["of"], "bugs_solved": row["bugs_solved"], "builds": row["builds"],
                                     "seconds": row["seconds"]}}
    out = {"frozen_at": time.strftime("%Y-%m-%d"), "rule": "highest selection score on the dev set; tie -> lower total time (PROGRESS.md)",
           "llama_cpp": LLAMA, "tiers": tiers}
    (ROOT / "model_manifests" / "frozen.json").write_text(json.dumps(out, indent=1) + "\n")
    for t, m in tiers.items():
        print(t, m["id"], m["sha256"][:16], m["selection"])


if __name__ == "__main__":
    main()
