"""Word documents: tables described in ordinary phrasing, and the owner's word range met by code (core proof D4/D5,
2 GB run 1: the table was left out and the length missed three times). Phrasings here are new, not the locked ones."""
import unittest

from neuron.agent.capabilities.writing import fit_words, parse_table, table_section


class TableParsing(unittest.TestCase):
    def test_listing_phrasing(self):
        t = parse_table("Include a table with the columns Part and Price (NGN) listing Brake pads 18000, Oil filter 4,500 and "
                        "Wiper blades 6000, and a Total row.")
        self.assertEqual(t["columns"], ["Part", "Price (NGN)"])
        self.assertEqual(t["rows"], [["Brake pads", 18000.0], ["Oil filter", 4500.0], ["Wiper blades", 6000.0]])
        self.assertTrue(t["total"])

    def test_colon_phrasing(self):
        t = parse_table("Add a table with the columns Shift and Hours: Morning 6, Afternoon 5, Night 8, and a Total row.")
        self.assertEqual([r[0] for r in t["rows"]], ["Morning", "Afternoon", "Night"])

    def test_old_phrasing_still_works(self):
        t = parse_table("The Costs section must have a table with the columns Item and Amount and these rows: Paint 30000, "
                        "Brushes 5000, then a total row.")
        self.assertEqual(t["section"], "Costs")
        self.assertEqual(len(t["rows"]), 2)

    def test_numbers_without_a_table_are_not_a_table(self):
        self.assertIsNone(parse_table("Write a note about the 3 new nurses and the 2 doctors who joined in 2026."))

    def test_unplaced_table_goes_where_its_rows_are_discussed(self):
        secs = [{"heading": "Background", "points": "who we are"}, {"heading": "Needs", "points": "brake pads and an oil filter"},
                {"heading": "Next steps", "points": "dates"}]
        t = parse_table("a table with the columns Part and Price listing Brake pads 18000, Oil filter 4500, and a Total row")
        self.assertEqual(table_section(t, secs), 1)


class WordRange(unittest.TestCase):
    def test_trims_whole_sentences_to_the_range_and_keeps_paragraphs(self):
        long = " ".join(f"Sentence number {i} has exactly seven words." for i in range(40))
        bodies = fit_words("A Title", [{"heading": "One"}, {"heading": "Two"}], [long + "\n\n" + long, long], 100, 200)
        n = len(" ".join(["A Title", "One", "Two"] + bodies).split())
        self.assertLessEqual(n, 200)
        self.assertGreaterEqual(n, 100)
        self.assertIn("\n\n", bodies[0])
        self.assertTrue(all(b.endswith(".") for b in bodies))


if __name__ == "__main__":
    unittest.main()
