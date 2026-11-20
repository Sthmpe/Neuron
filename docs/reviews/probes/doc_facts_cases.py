"""Invented document-check probes (not from any locked set): (question, answer, quote, should_accept)."""
import json, sys
CASES = [
 ("How many yellow chairs are there?", "3", "There are 16 blue chairs and 3 yellow chairs.", True),
 ("How many staff does the bakery employ?", "The bakery employs 12 staff.", "The bakery employs 12 staff and 2 drivers.", True),
 ("What was the library's income in 2025?", "4.2 million naira", "Income in 2025 was 4.2 million naira, of which donations were 1.1 million naira.", True),
 ("How much does a day ticket cost?", "2,500 naira", "A day ticket costs 2,500 naira; a week ticket costs 12,000 naira.", True),
 ("When does the market open?", "7am", "The market opens at 7am and closes at 6pm.", True),
 ("How many patients were seen in March?", "310", "In March, the clinic saw 310 patients.", True),
 ("Who chairs the board?", "Mrs Okafor", "The board is chaired by Mrs Okafor.", True),
 ("How many trucks does the company own?", "9", "The company owns 9 trucks.", True),
 ("How many members joined in 2024?", "45", "45 new members joined in 2024.", True),
 ("What is the capacity of the hall?", "300 people", "The hall holds 300 people.", True),
 ("How many yellow chairs are there?", "16 yellow chairs.", "There are 16 blue chairs and 3 yellow chairs.", False),
 ("How many drivers does the bakery employ?", "12", "The bakery employs 12 staff and 2 drivers.", False),
 ("What were the donations in 2025?", "4.2 million naira", "Income in 2025 was 4.2 million naira, of which donations were 1.1 million naira.", False),
 ("How much does a week ticket cost?", "2,500 naira", "A day ticket costs 2,500 naira; a week ticket costs 12,000 naira.", False),
 ("When does the market close?", "7am", "The market opens at 7am and closes at 6pm.", False),
 ("How many trucks does the company own?", "12", "The company owns 9 trucks.", False),
 ("How many members joined in 2024?", "2024", "45 new members joined in 2024.", False),
 ("What is the capacity of the hall?", "250 people", "The hall holds 300 people.", False),
]
def run(fn):
    out = []
    for q, a, quote, want in CASES:
        try:
            got = bool(fn(q, a, quote))
        except Exception as e:
            got = f"error {type(e).__name__}"
        out.append({"q": q, "a": a, "want": want, "got": got})
    return out
