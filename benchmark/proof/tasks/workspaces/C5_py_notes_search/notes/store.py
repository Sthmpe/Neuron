import json
from pathlib import Path


def load(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else []


def save(path, notes):
    Path(path).write_text(json.dumps(notes, indent=1))


def add(path, title, body):
    notes = load(path)
    notes.append({"title": title, "body": body})
    save(path, notes)
