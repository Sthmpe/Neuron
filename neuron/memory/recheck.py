"""Rechecking old notes when the internet is back.

Notes that came from outside (a registry, a web page) can go stale. When online, NEURON looks at notes not checked for
a while (30 days by default):
  package notes ("six 1.17.0 is the newest release on PyPI")   asked again at the registry; if a newer release exists the
                                                                old note is marked outdated (never deleted) and a new one saved
  notes from a web page                                         the page is fetched; if it is gone (404/410) the note is
                                                                marked unverified, otherwise its check date is renewed
  anything else                                                 left as it is
Outdated notes are kept for history but no longer returned by search.
"""
import re
import time
import urllib.error
import urllib.request

from ..online import packages


def _page_alive(url, timeout=20):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "NEURON-local-assistant/0.1 (note recheck)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except urllib.error.HTTPError as e:
        return e.code not in (404, 410)
    except (urllib.error.URLError, OSError):
        return None                     # could not tell (network trouble): leave the note as it is


def recheck(memory, days=30, fetch=packages.fetch_json, alive=_page_alive, log=print):
    out = {"checked": 0, "outdated": 0, "unverified": 0, "unchanged": 0, "skipped": 0}
    for n in memory.due_for_recheck(days):
        tags = (n.get("tags") or "").split()
        try:
            if "package" in tags and re.match(r"https://(pypi\.org|registry\.npmjs\.org)/", n["source"] or ""):
                manager = "pip" if "pypi.org" in n["source"] else "npm"
                name = n["source"].rstrip("/").split("/")[-2] if manager == "pip" else n["source"].rstrip("/").split("/")[-2]
                info = packages.latest({"manager": manager, "name": name}, fetch)
                newest = info["version"]
                if newest and newest != n["version"] and packages.version_tuple(newest):
                    memory.mark(n["id"], status="outdated")
                    memory.add("fact", f"{name} {newest} is the newest stable release on {'PyPI' if manager == 'pip' else 'npm'} "
                                       f"(checked {time.strftime('%Y-%m-%d')}); replaces the note about {n['version']}.",
                               n["source"], version=newest, verified=True, tags=("package", manager, name))
                    out["outdated"] += 1
                    log(f"  memory: {name} {n['version']} -> {newest}, old note marked outdated")
                else:
                    memory.mark(n["id"], status=n["status"])
                    out["unchanged"] += 1
            elif (n["source"] or "").startswith("http"):
                ok = alive(n["source"])
                if ok is None:
                    out["skipped"] += 1
                    continue
                memory.mark(n["id"], status=n["status"] if ok else "unverified")
                out["unchanged" if ok else "unverified"] += 1
            else:
                out["skipped"] += 1
                continue
            out["checked"] += 1
        except Exception as e:          # noqa: BLE001  one bad note never stops the others
            out["skipped"] += 1
            log(f"  memory recheck of note {n['id']} failed: {type(e).__name__}")
    return out
