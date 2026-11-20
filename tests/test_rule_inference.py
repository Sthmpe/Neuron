"""A rule the owner described but the planner left out is built from the request's words, or reported as not built
(core proof A1, 2 GB: no stock rule, still VERIFIED). Invented examples, not the locked tasks."""
import unittest

from neuron.builder.relations import infer_missing_rule, plain_threshold_labels


def spec(rules=()):
    return {"entities": [
        {"name": "parts", "label": "Parts", "search_field": "name", "fields": [
            {"name": "name", "type": "text"}, {"name": "price", "type": "number"}, {"name": "on_hand", "type": "number"}]},
        {"name": "orders", "label": "Orders", "search_field": "client", "fields": [
            {"name": "part", "type": "link", "to": "parts"}, {"name": "client", "type": "text"}, {"name": "qty", "type": "number"}]}],
        "rules": list(rules),
        "dashboard": [{"label": "Parts on hand", "entity": "parts", "kind": "count_below", "field": "on_hand", "below": 5}]}


class RuleInference(unittest.TestCase):
    def test_builds_the_rule_the_request_describes(self):
        r, why = infer_missing_rule("Keep parts and orders. An order takes the quantity off the part's stock and is refused "
                                    "if there are not enough parts.", spec())
        self.assertEqual((r["on_add"], r["link_field"], r["target_field"], r["amount_field"], r["change"], r["block_if_negative"]),
                         ("orders", "part", "on_hand", "qty", "subtract", True))
        self.assertIn("from the request", why)

    def test_price_is_never_the_stock(self):
        r, _ = infer_missing_rule("Each order lowers the part's count.", spec())
        self.assertEqual(r["target_field"], "on_hand")

    def test_no_change_words_no_rule(self):
        self.assertEqual(infer_missing_rule("Keep parts and orders. Search orders by client.", spec()), (None, ""))

    def test_an_existing_rule_is_left_alone(self):
        self.assertEqual(infer_missing_rule("An order lowers the stock.", spec(rules=[{"on_add": "orders"}]))[0], None)

    def test_a_count_below_a_threshold_says_so(self):
        s = spec()
        notes = plain_threshold_labels(s)
        self.assertEqual(s["dashboard"][0]["label"], "Parts with fewer than 5 on hand")
        self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()
