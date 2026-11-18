"""Pictures for a project: fetch licensed photos for the slots that still show an 'Image needed' placeholder.

Any step that builds something with pictures (a website, later documents and slides) prepares the slots offline
(neuron.media.images.prepare: owner photos first, labelled placeholders for the rest) and adds this step to the plan.
It needs the internet, so offline it waits and the job resumes it by itself when the connection is back.
"""
from pathlib import Path

from ...media import images
from ..capability import Capability, Outcome, Verdict


class FindImages(Capability):
    name = "find_images"
    purpose = "Replace 'Image needed' placeholders with suitable licensed photos and record where each came from"
    inputs = {"project": {"type": "path", "required": True, "description": "folder with images.json"}}
    needs_internet = True
    permissions = ("network", "write_workspace")
    verification = "each filled slot has a real photo file, an allowed licence, an author/page record and a credits line"
    domains = ("media", "web")
    planner_visible = False
    provider_factory = images.CommonsProvider          # replaceable in tests

    def run(self, job, params):
        project = job.workspace / params["project"]
        m = images.Manifest(project, params.get("image_dir", "static/images"))
        if not m.slots:
            return Outcome(True, "no pictures needed", {"filled": [], "not_found": []})
        r = images.fetch_licensed(m, self.provider_factory(), job.effects, log=job.log)
        left = [s["slot"] for s in m.needed()]
        summary = (f"{len(r['filled'])} licensed photo(s) added ({', '.join(r['filled']) or 'none'})"
                   + (f"; still needed: {', '.join(left)}" if left else ""))
        evidence = {"retry_later": r["retry_after"], "why": "Wikimedia Commons asked NEURON to slow down"} if r.get("retry_after") else {}
        return Outcome(True, summary, {**r, "still_needed": left}, files=[str(Path(params["project"]) / "IMAGE_CREDITS.md")],
                       evidence=evidence)

    def verify(self, job, params, outcome):
        project = job.workspace / params["project"]
        m = images.Manifest(project)
        checks = []
        for s in m.slots:
            if s["status"] == "licensed":
                src = s.get("source") or {}
                f = project / s["file"]
                checks.append({"id": f"{s['slot']}_photo", "pass": f.exists() and f.stat().st_size > 1000 and f.suffix in images.PHOTO_EXT,
                               "detail": s["file"]})
                checks.append({"id": f"{s['slot']}_licence", "pass": bool(images.LICENCE_OK.search(src.get("licence", ""))
                                                                            and not images.LICENCE_BAD.search(src.get("licence", ""))),
                               "detail": src.get("licence", "")})
                checks.append({"id": f"{s['slot']}_source", "pass": bool(src.get("page")) and src["page"] in (project / "IMAGE_CREDITS.md").read_text(),
                               "detail": src.get("page", "")})
            elif s["status"] == "needed":
                checks.append({"id": f"{s['slot']}_found", "pass": False, "gap": True,
                               "detail": f"images needed: no suitable licensed photo found for {s['slot']} ({s['purpose']})"})
        return Verdict(all(c["pass"] for c in checks), checks, "files, licences and the credits file checked")


CAPABILITIES = [FindImages()]
