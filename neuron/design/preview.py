"""Build a page from a spec + design with the new kit and serve it from the sandbox, for checks and screenshots."""
import json
import shutil
from pathlib import Path

KIT = Path(__file__).resolve().parents[1] / "kit_next"
APP_PY = '''from kit.web import App
import schema

app = App({name!r})
schema.setup(app)
app.load_pages("pages")

if __name__ == "__main__":
    app.run()
'''


def make_project(folder, spec, design, files):
    folder = Path(folder)
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "pages").mkdir(parents=True)
    shutil.copytree(KIT, folder / "kit", ignore=shutil.ignore_patterns("__pycache__"))
    (folder / "pages" / "__init__.py").touch()
    (folder / "app.py").write_text(APP_PY.format(name=spec["app_name"]))
    (folder / "theme.json").write_text(json.dumps(design, indent=1))
    for rel, code in files.items():
        (folder / rel).write_text(code)
    return folder
