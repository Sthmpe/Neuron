import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from stock.export import to_csv
from stock.items import Item


class Hidden(unittest.TestCase):
    def test_to_csv(self):
        text = to_csv([Item("rice", 3, 5), Item("beans", 9, 5)])
        self.assertEqual(text.strip().splitlines(), ["name,on_hand,reorder_level,reorder", "beans,9,5,no", "rice,3,5,yes"])

    def test_command(self):
        f = Path(tempfile.mkdtemp()) / "items.json"
        f.write_text(json.dumps([{"name": "salt", "on_hand": 2, "reorder_level": 2}]))
        out = subprocess.run([sys.executable, "-m", "stock.export", str(f)], capture_output=True, text=True).stdout
        self.assertEqual(out.strip().splitlines(), ["name,on_hand,reorder_level,reorder", "salt,2,2,yes"])
