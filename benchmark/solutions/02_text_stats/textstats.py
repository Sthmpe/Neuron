"""Simple text statistics."""
from collections import Counter


def words(text):
    """Lower-cased words of the text, with surrounding punctuation removed."""
    cleaned = []
    for raw in text.lower().split():
        word = raw.strip(".,;:!?\"'()")
        if word:
            cleaned.append(word)
    return cleaned


def word_count(text):
    return len(words(text))


def most_common(text, n=3):
    """The n most frequent words as (word, count), ties broken alphabetically."""
    counts = Counter(words(text))
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def average_word_length(text):
    ws = words(text)
    if not ws:
        return 0.0
    return sum(len(w) for w in ws) / len(ws)
