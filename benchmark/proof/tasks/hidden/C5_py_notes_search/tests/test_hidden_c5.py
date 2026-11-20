import os
import subprocess
import sys
import tempfile
import unittest

from notes.search import find


class Hidden(unittest.TestCase):
    def test_find(self):
        notes = [{"title": "Shopping", "body": "Rice and OIL"}, {"title": "Oil change", "body": "car"}, {"title": "Calls", "body": "x"}]
        self.assertEqual([n["title"] for n in find(notes, "oil")], ["Shopping", "Oil change"])
        self.assertEqual(find(notes, "zzz"), [])

    def test_command(self):
        env = dict(os.environ, NOTES_FILE=os.path.join(tempfile.mkdtemp(), "n.json"))
        run = lambda *a: subprocess.run([sys.executable, "-m", "notes.cli", *a], capture_output=True, text=True, env=env).stdout
        run("add", "Market", "buy TOMATOES")
        run("add", "Rent", "pay on Friday")
        self.assertEqual(run("search", "tomatoes").strip(), "Market")
        self.assertEqual(run("search", "bicycle").strip(), "no notes found")
