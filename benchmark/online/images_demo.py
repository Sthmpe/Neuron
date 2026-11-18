"""Real photo search for a bakery website: placeholders offline, then licensed photos from Wikimedia Commons.

  python3 -m benchmark.online.images_demo
Records what was chosen, its licence, author and page, and what was refused and why.
"""
import json
import shutil
import tempfile
import time
from pathlib import Path

from neuron.agent.effects import Effects
from neuron.media import images

ROOT = Path(__file__).resolve().parents[2]
SLOTS = [{"slot": "hero", "purpose": "fresh bread on the counter", "query": "artisan bread loaves", "shape": "wide"},
         {"slot": "pastries", "purpose": "a tray of pastries", "query": "croissants pastries tray", "shape": "wide"},
         {"slot": "baker", "purpose": "a baker shaping dough", "query": "baker kneading dough hands", "shape": "wide"}]


def main():
    p = Path(tempfile.mkdtemp(prefix="images-demo-")) / "bakery"
    m = images.prepare(p, SLOTS, ("#e9b48f", "#7a3e2a", "#c2603e"))
    offline = m.summary()
    t0 = time.time()
    r = images.fetch_licensed(m, images.CommonsProvider(), Effects(p / ".neuron" / "e.jsonl"))
    m = images.Manifest(p)
    out = {"offline": offline, "online": m.summary(), "seconds": round(time.time() - t0, 1), "not_found": r["not_found"],
           "rate_limited_retry_after_s": r.get("retry_after"), "run_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "chosen": [{"slot": s["slot"], **{k: (s.get("source") or {}).get(k) for k in ("title", "author", "licence", "licence_url", "page")},
                       "bytes": (p / s["file"]).stat().st_size if s.get("file") and (p / s["file"]).exists() else 0} for s in m.slots],
           "credits": (p / "IMAGE_CREDITS.md").read_text()}
    (ROOT / "benchmark" / "results" / "online_images_demo.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:4000])
    shutil.rmtree(p.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
