"""Who is this for, and what should they feel? That mood drives every later choice.

Each mood is plain data: the words that point to it, what the visitor should feel, several good
palettes (so results vary but always fit), several font pairings, shape, depth, rhythm and the
layout variants that suit it. Adding a mood or a palette is a data change, not a code change."""
import re

# palette = (name, dominant, support, accent): dominant tints most of the page, support carries bands
# and strong areas, accent is kept small for actions.
MOODS = {
    "trust": {
        "feel": "trust and calm confidence",
        "for": "professional services where people hand over something important",
        "words": "law lawyer lawyers attorney solicitor legal firm accountant accounting audit tax insurance "
                 "consulting consultant advisory advisor adviser wealth financial planner notary bank estate "
                 "property realtor surveyor architect",
        "palettes": [("Navy and brass", "#1d3557", "#1d3557", "#b08d57"), ("Forest and sand", "#1f4d3a", "#1f4d3a", "#b98a4b"),
                     ("Ink and teal", "#1e293b", "#1e293b", "#0f766e"), ("Oxblood and stone", "#5c1f24", "#5c1f24", "#5c1f24"),
                     ("Charcoal and emerald", "#2b2f36", "#2b2f36", "#047857")],
        "fonts": [("source-serif-4", "inter"), ("cormorant-garamond", "manrope"), ("playfair-display", "libre-franklin"),
                  ("libre-franklin", "libre-franklin")],
        "radius": 6, "button": "rounded", "shadow": "crisp", "ratio": 1.25, "space": 1.15,
        "hero": ["editorial", "split", "card"], "features": ["list", "cards", "rows"], "fact": ["inline", "panel"],
        "form": ["split", "panel"], "nav": ["bar", "minimal"], "rhythm": ["alternate", "flow"],
    },
    "warmth": {
        "feel": "warmth, appetite and welcome",
        "for": "food and hospitality, where people should feel at home",
        "words": "bakery baker bakes bread cake cakes pastry pastries cafe café coffee restaurant kitchen catering "
                 "caterer food chef bistro pizzeria pizza grill bar brunch deli dessert desserts sweets chocolate "
                 "confectionery ice cream tea juice smoothie pies meals cooking cook dinner lunch breakfast",
        "palettes": [("Terracotta and cream", "#e9b48f", "#7a3e2a", "#c2603e"), ("Caramel and espresso", "#d9a066", "#4b2e22", "#b4532a"),
                     ("Tomato and olive", "#e6a07d", "#4f5d2f", "#c8432b"), ("Honey and berry", "#e8b65c", "#6b2a3d", "#9e2a4b"),
                     ("Butter and cocoa", "#e8c872", "#5b3a29", "#8a4b2a")],
        "fonts": [("fraunces", "figtree"), ("lora", "dm-sans"), ("bricolage-grotesque", "figtree"), ("instrument-serif", "dm-sans")],
        "radius": 18, "button": "pill", "shadow": "soft", "ratio": 1.25, "space": 1.0,
        "hero": ["split", "centered", "card"], "features": ["cards", "tiles", "rows"], "fact": ["callout", "panel"],
        "form": ["band", "split", "panel"], "nav": ["floating", "bar"], "rhythm": ["alternate", "bands"],
    },
    "clarity": {
        "feel": "clarity, precision and momentum",
        "for": "technology and finance products, where people must understand fast",
        "words": "fintech app apps software saas startup platform api data analytics dashboard payments payment "
                 "wallet crypto tech technology digital cloud ai automation developer developers product tool "
                 "tools banking invoices invoicing budgeting",
        "palettes": [("Cobalt", "#1f4fbf", "#0b1f4d", "#1f4fbf"), ("Emerald ledger", "#0e7c66", "#0b2e2a", "#0e7c66"),
                     ("Ink and coral", "#22304a", "#22304a", "#e5533d"), ("Deep teal", "#0f766e", "#134e4a", "#0f766e"),
                     ("Graphite and azure", "#3b3f45", "#111827", "#2a7fd6")],
        "fonts": [("manrope", "inter"), ("plus-jakarta-sans", "inter"), ("sora", "inter"), ("inter", "inter")],
        "radius": 12, "button": "rounded", "shadow": "crisp", "ratio": 1.2, "space": 1.0,
        "hero": ["split", "editorial", "centered"], "features": ["cards", "list", "steps"], "fact": ["inline", "callout"],
        "form": ["split", "panel"], "nav": ["bar", "floating"], "rhythm": ["flow", "alternate"],
    },
    "calm": {
        "feel": "calm, care and reassurance",
        "for": "health and wellbeing, where people arrive anxious and should relax",
        "words": "spa wellness yoga pilates meditation therapy therapist counselling counseling clinic dental "
                 "dentist doctor health healthcare physio physiotherapy massage skincare nurse nursing care "
                 "retreat mindfulness psychologist optician pharmacy",
        "palettes": [("Sage and sand", "#b9c9b2", "#3f5a45", "#4d6b52"), ("Mist and clay", "#b4c6d4", "#2f4858", "#a8674c"),
                     ("Eucalyptus and blush", "#a9c6bb", "#2e5249", "#b56b6b"), ("Linen and stone", "#d8cbb8", "#4a4238", "#6b5d4f")],
        "fonts": [("cormorant-garamond", "manrope"), ("lora", "figtree"), ("fraunces", "manrope")],
        "radius": 22, "button": "pill", "shadow": "soft", "ratio": 1.25, "space": 1.2,
        "hero": ["centered", "editorial", "split"], "features": ["list", "tiles", "cards"], "fact": ["callout", "inline"],
        "form": ["panel", "split"], "nav": ["minimal", "floating"], "rhythm": ["flow", "alternate"],
    },
    "energy": {
        "feel": "energy, drive and excitement",
        "for": "sport, fitness and events, where people should feel ready to move",
        "words": "gym fitness training trainer workout crossfit boxing martial sports sport football basketball "
                 "running club athletes event events festival concert party nightclub music band dance esports",
        "palettes": [("Volt", "#3b3f45", "#141414", "#b9f227"), ("Red line", "#2a2f3a", "#111827", "#e0301e"),
                     ("Cobalt and sun", "#1f4fbf", "#0b1f4d", "#f4c430"), ("Magenta night", "#2b2140", "#1c1530", "#d6246e")],
        "fonts": [("outfit", "inter"), ("bricolage-grotesque", "dm-sans"), ("sora", "dm-sans")],
        "radius": 10, "button": "pill", "shadow": "lifted", "ratio": 1.333, "space": 0.95,
        "hero": ["banner", "editorial", "split"], "features": ["tiles", "cards", "steps"], "fact": ["callout", "inline"],
        "form": ["band", "split"], "nav": ["bar", "minimal"], "rhythm": ["bands", "alternate"],
    },
    "elegance": {
        "feel": "elegance, exclusivity and quiet luxury",
        "for": "beauty, fashion and luxury, where restraint signals quality",
        "words": "fashion boutique jewellery jewelry jeweller luxury salon beauty bridal wedding weddings hotel "
                 "resort florist perfume interior interiors photography photographer couture tailor gallery "
                 "art designer wine champagne",
        "palettes": [("Noir and champagne", "#e9d8b4", "#151515", "#151515"), ("Emerald and gilt", "#0f4d3c", "#0f4d3c", "#a8844e"),
                     ("Rose and taupe", "#d9b3ab", "#4f413d", "#4f413d"), ("Ivory and plum", "#e8dccb", "#4a2340", "#4a2340")],
        "fonts": [("playfair-display", "manrope"), ("cormorant-garamond", "figtree"), ("instrument-serif", "manrope")],
        "radius": 2, "button": "sharp", "shadow": "whisper", "ratio": 1.333, "space": 1.25,
        "hero": ["editorial", "centered", "banner"], "features": ["rows", "list", "tiles"], "fact": ["inline", "callout"],
        "form": ["panel", "split"], "nav": ["minimal", "bar"], "rhythm": ["flow", "alternate"],
    },
    "playful": {
        "feel": "fun, friendliness and delight",
        "for": "children, pets and parties, where joy is the point",
        "words": "kids children child toy toys nursery playgroup daycare pets pet puppy dog cat grooming party "
                 "parties balloons games candy birthday creche playground",
        "palettes": [("Sunny", "#f4c430", "#1d4e89", "#1d4e89"), ("Coral and teal", "#f6a596", "#0f5f63", "#e5533d"),
                     ("Grass and tangerine", "#9fd18b", "#1f5a3d", "#e0701c"), ("Sky and berry", "#8cc7f0", "#1d3c6e", "#c2185b")],
        "fonts": [("nunito", "nunito"), ("bricolage-grotesque", "nunito"), ("outfit", "figtree")],
        "radius": 24, "button": "pill", "shadow": "soft", "ratio": 1.25, "space": 1.0,
        "hero": ["card", "split", "centered"], "features": ["tiles", "cards"], "fact": ["callout", "panel"],
        "form": ["band", "panel"], "nav": ["floating", "bar"], "rhythm": ["bands", "alternate"],
    },
    "natural": {
        "feel": "freshness, honesty and growth",
        "for": "gardens, farms and the outdoors, where people want something real",
        "words": "garden gardening gardener landscaping landscape farm farmer organic eco green plants plant "
                 "nursery flowers outdoor outdoors camping hiking trees lawn mowing agriculture vegetables "
                 "produce sustainable environmental",
        "palettes": [("Moss and terracotta", "#a7b48a", "#2f3d23", "#a8492a"), ("Pine and wheat", "#e2d1a8", "#2b5d45", "#2b5d45"),
                     ("Olive and clay", "#b9bf8f", "#3d4521", "#9e5d40"), ("Leaf and sky", "#a8d0b0", "#1f4d33", "#2f7d4a")],
        "fonts": [("fraunces", "dm-sans"), ("lora", "figtree"), ("bricolage-grotesque", "dm-sans")],
        "radius": 14, "button": "pill", "shadow": "soft", "ratio": 1.25, "space": 1.05,
        "hero": ["split", "card", "editorial"], "features": ["cards", "rows", "list"], "fact": ["panel", "callout"],
        "form": ["split", "band"], "nav": ["bar", "floating"], "rhythm": ["alternate", "flow"],
    },
    "dependable": {
        "feel": "reliability, competence and straight talk",
        "for": "trades and home services, where people need it done right, today",
        "words": "plumber plumbing electrician electrical builder building construction roofing roofer mechanic "
                 "garage repair repairs cleaning cleaner cleaners handyman painter painting decorating carpenter "
                 "joinery locksmith hvac removals movers moving logistics courier delivery transport haulage",
        "palettes": [("Safety orange", "#4a5768", "#1e2832", "#d9480f"), ("Cobalt and yellow", "#1f4fbf", "#102a5c", "#f4c430"),
                     ("Forest and graphite", "#3b3f45", "#1f2a24", "#2f8f4e")],
        "fonts": [("outfit", "inter"), ("libre-franklin", "inter"), ("manrope", "inter")],
        "radius": 8, "button": "rounded", "shadow": "crisp", "ratio": 1.2, "space": 0.95,
        "hero": ["banner", "split"], "features": ["list", "cards", "steps"], "fact": ["inline", "panel"],
        "form": ["split", "band"], "nav": ["bar"], "rhythm": ["alternate", "bands"],
    },
    "bright": {
        "feel": "encouragement, curiosity and progress",
        "for": "learning and coaching, where people want to grow",
        "words": "tutor tutors tutoring tuition lessons lesson school academy classes class course courses teacher "
                 "teaching students learning education coaching coach mentor exam exams maths math science "
                 "language languages music lessons",
        "palettes": [("Royal and sunflower", "#2747c4", "#14245f", "#2747c4"), ("Teal and coral", "#0f7c80", "#0b3d40", "#d9483b"),
                     ("Ink and tangerine", "#22304a", "#22304a", "#e06a12"), ("Forest and gold", "#2d6a4f", "#1b4332", "#2d6a4f")],
        "fonts": [("plus-jakarta-sans", "figtree"), ("bricolage-grotesque", "figtree"), ("fraunces", "plus-jakarta-sans")],
        "radius": 16, "button": "pill", "shadow": "soft", "ratio": 1.25, "space": 1.0,
        "hero": ["split", "card", "centered"], "features": ["cards", "steps", "list"], "fact": ["callout", "panel"],
        "form": ["split", "panel", "band"], "nav": ["bar", "floating"], "rhythm": ["alternate", "flow"],
    },
    "modern": {
        "feel": "a clean, modern and confident first impression",
        "for": "a business whose field the request does not make clear",
        "words": "",
        "palettes": [("Cobalt", "#1f4fbf", "#0b1f4d", "#1f4fbf"), ("Charcoal and emerald", "#2b2f36", "#2b2f36", "#047857"),
                     ("Ink and coral", "#22304a", "#22304a", "#e5533d"), ("Linen and stone", "#d8cbb8", "#4a4238", "#6b5d4f")],
        "fonts": [("manrope", "inter"), ("plus-jakarta-sans", "figtree"), ("fraunces", "inter")],
        "radius": 12, "button": "rounded", "shadow": "soft", "ratio": 1.25, "space": 1.05,
        "hero": ["split", "editorial", "centered", "card"], "features": ["cards", "list", "tiles"], "fact": ["callout", "inline"],
        "form": ["split", "panel"], "nav": ["bar", "floating"], "rhythm": ["alternate", "flow"],
    },
}
WEAK = {"dashboard", "class", "classes", "course", "courses", "lesson", "lessons", "students", "learning", "care", "app", "apps", "digital",
        "product", "tool", "tools", "platform", "club", "party", "parties", "green", "eco", "event", "events", "design",
        "designer", "art", "wine", "data", "tech", "technology", "building", "moving", "delivery", "music", "dance", "plant",
        "plants", "flowers", "health", "cooking", "cook", "tea", "bar", "firm", "property", "estate", "children", "child"}
APP_WORDS = "dashboard stock inventory customers records orders invoices staff students patients bookings members"


def detect(request):
    """(mood, reason). Counts the words that point to each mood; the strongest wins. 'modern' when none do."""
    text = request.lower()
    scores = {}
    for name, m in MOODS.items():
        hits = [w for w in m["words"].split() if re.search(rf"\b{re.escape(w)}\b", text)]
        if hits:
            scores[name] = hits
    if not scores:
        return "modern", "Nothing in the request names the kind of business, so the design aims for " + MOODS["modern"]["feel"] + "."
    weight = lambda hits: sum(1 if w in WEAK else 3 for w in hits)     # the specific trade counts more than generic words
    best = max(scores, key=lambda k: (weight(scores[k]), -list(MOODS).index(k)))
    words = ", ".join(f'"{w}"' for w in scores[best][:3])
    return best, (f"The request mentions {words}: this is {MOODS[best]['for']}, so the design should give "
                  f"{MOODS[best]['feel']}.")
