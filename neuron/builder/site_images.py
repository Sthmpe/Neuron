"""Which pictures a website needs, and what to search for. Curated data, not the model's guess.

A site gets three pictures: one leading the page (hero) and a row of two after the first section. The search words
come from the kind of business named in the request; the owner's own photos always take precedence
(neuron.media.images.prepare). Offline, each slot shows a labelled "Image needed" placeholder in the site's colours.
"""
import re

# kind of business -> (words that name it, [hero search, photo 1 search, photo 2 search], [what each picture shows])
KINDS = [
    ("bakery", r"bak(ery|er|es|ed)|bread|pastr|cake|patisserie",
     ["artisan bread loaves", "pastries bakery display", "baker kneading dough"],
     ["Fresh bread", "Pastries on display", "Dough being shaped by hand"]),
    ("law", r"\blaw\b|lawyer|solicitor|attorney|legal|barrister|chambers",
     ["law books library", "lawyer office desk documents", "courthouse columns"],
     ["Law books", "A lawyer's desk with papers", "Court building"]),
    ("salon", r"salon|hair|barber|braid|stylist|beauty|nail|spa\b",
     ["hair salon interior", "hairdresser cutting hair", "hair styling tools"],
     ["The salon", "A hairdresser at work", "Styling tools"]),
    ("cafe", r"\bcaf[eé]\b|coffee|espresso|roaster",
     ["coffee shop interior", "barista pouring coffee", "coffee beans"], ["The cafe", "A barista at work", "Coffee beans"]),
    ("restaurant", r"restaurant|bistro|grill|kitchen|catering|chef|eatery|food",
     ["restaurant dining room", "chef plating food", "fresh ingredients market"], ["The dining room", "A chef at work", "Fresh ingredients"]),
    ("garden", r"garden|landscap|lawn|plant|nursery",
     ["landscaped garden", "gardener pruning hedge", "garden flowers"], ["A garden", "Pruning a hedge", "Flowers"]),
    ("clinic", r"clinic|dental|dentist|doctor|physio|pharmacy|health",
     ["medical clinic reception", "doctor consultation", "dental clinic"], ["The clinic", "A consultation", "Treatment room"]),
    ("fitness", r"gym|fitness|yoga|pilates|trainer",
     ["gym interior equipment", "yoga class", "personal trainer"], ["The gym", "A class", "Training"]),
    ("repair", r"repair|mechanic|garage|plumb|electric|fix",
     ["workshop tools bench", "mechanic repairing", "tools on wall"], ["The workshop", "A repair in progress", "Tools"]),
    ("tailor", r"tailor|fashion|boutique|clothing|sewing",
     ["tailor sewing", "fabric rolls", "clothing boutique"], ["Tailoring", "Fabrics", "The boutique"]),
]


def kind_of(request, app_name=""):
    text = f"{request} {app_name}".lower()
    for kind, words, queries, shows in KINDS:
        if re.search(words, text):
            return kind, queries, shows
    nouns = [w for w in re.findall(r"[a-z]{4,}", (app_name or request).lower())
             if w not in {"website", "page", "site", "business", "company", "small", "with", "that", "show", "need"}][:2]
    q = " ".join(nouns) or "small business"
    return "business", [q, q + " work", q + " detail"], ["A photo of the business", "At work", "A detail"]


def slots(request, spec):
    """Three slots for a site: hero (wide) and two photos for the row after the first section."""
    kind, queries, shows = kind_of(request, spec.get("app_name", ""))
    names = ("hero", "photo1", "photo2")
    return [{"slot": n, "purpose": shows[i], "query": queries[i], "shape": "wide"} for i, n in enumerate(names)]
