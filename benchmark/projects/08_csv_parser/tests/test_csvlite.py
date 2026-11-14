import unittest

import csvlite


class CsvTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(csvlite.parse_line("a,b,c"), ["a", "b", "c"])

    def test_quoted_delimiter(self):
        self.assertEqual(csvlite.parse_line('x,"hello, world",z'), ["x", "hello, world", "z"])

    def test_escaped_quote(self):
        self.assertEqual(csvlite.parse_line('"say ""hi""",b'), ['say "hi"', "b"])

    def test_empty_field_in_the_middle(self):
        self.assertEqual(csvlite.parse_line("a,,c"), ["a", "", "c"])

    def test_empty_last_field(self):
        self.assertEqual(csvlite.parse_line("a,b,"), ["a", "b", ""])

    def test_rows_keep_all_columns(self):
        rows = csvlite.parse("name,city,phone\nAda,Lagos,\nBen,Abuja,123\n")
        self.assertEqual(rows[0], {"name": "Ada", "city": "Lagos", "phone": ""})
        self.assertEqual(rows[1]["phone"], "123")

    def test_other_delimiter(self):
        self.assertEqual(csvlite.parse_line("a;b;c", ";"), ["a", "b", "c"])
