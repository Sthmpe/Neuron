import os
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "notes.cli", *args], capture_output=True, text=True, env=self.env).stdout

    def setUp(self):
        self.env = dict(os.environ, NOTES_FILE=os.path.join(tempfile.mkdtemp(), "n.json"))

    def test_add_and_list(self):
        self.assertEqual(self.run_cli("add", "Shopping", "rice and oil").strip(), "added")
        self.run_cli("add", "Calls", "ring the landlord")
        self.assertEqual(self.run_cli("list").split(), ["Shopping", "Calls"])
