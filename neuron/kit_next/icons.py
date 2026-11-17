"""Icons chosen by rule from the words of an item, never by a model and never at random.
If no rule matches, the caller shows a quiet number instead: a wrong icon is worse than none."""
import json
import re
from functools import lru_cache
from pathlib import Path

RULES = [
    (r"bread|loaf|loaves|sourdough|baguette|wheat|grain|flour", "wheat"), (r"birthday|celebration", "cake"),
    (r"cake|cupcake|gateau", "cake-slice"), (r"pie|pastry|pastries|croissant|puff", "croissant"), (r"pizza", "pizza"),
    (r"coffee|espresso|latte|cappuccino|cafe|café", "coffee"), (r"tea|juice|smoothie|drink", "cup-soda"),
    (r"cookie|biscuit", "cookie"), (r"ice cream|gelato", "ice-cream-cone"), (r"soup|stew", "soup"), (r"salad|vegan|vegetable", "salad"),
    (r"sandwich|burger|snack", "sandwich"), (r"meat|grill|bbq|steak|suya", "beef"), (r"chef|cook|kitchen|catering|meal", "chef-hat"),
    (r"menu|dinner|lunch|breakfast|dining|restaurant|food", "utensils"),
    (r"math|maths|algebra|calculus|account|bookkeep|tax", "calculator"), (r"physics|chemistry|science|atom", "atom"),
    (r"english|reading|literature|writing|essay|book", "book-open"), (r"language|french|spanish|yoruba|igbo|hausa|translat", "languages"),
    (r"exam|graduat|degree|university|school|class|course|lesson|tutor", "graduation-cap"),
    (r"law|legal|court|litigat|dispute", "scale"), (r"contract|document|paperwork|will\b|probate|deed", "file-text"),
    (r"property|real estate|conveyanc|house|home|rent|apartment", "house"), (r"business|company|corporate|commercial", "briefcase"),
    (r"insur|protect|secur|safe", "shield-check"), (r"family|divorce|child custody|people|team|staff|community", "users"),
    (r"invest|growth|grow|wealth|profit", "trending-up"), (r"pay|payment|wallet|money|cash|transfer", "wallet"),
    (r"card|credit|debit", "credit-card"), (r"saving|savings|budget", "piggy-bank"), (r"price|pricing|fee|cost|rate|naira|dollar|\$|₦", "tag"),
    (r"report|analytic|dashboard|insight|chart|data", "chart-column"), (r"invoice|receipt|billing", "receipt"),
    (r"garden|plant|flower|florist|bouquet", "flower-2"), (r"tree|hedge|prun|forest", "trees"), (r"lawn|mow|grass|leaf|organic|eco", "leaf"),
    (r"seed|grow|farm|harvest|sprout", "sprout"), (r"water|irrigat|clean|wash", "droplets"), (r"sun|summer|outdoor", "sun"),
    (r"hair|cut|barber|salon|scissor|tailor", "scissors"), (r"beauty|makeup|nail|skincare|glow", "sparkles"),
    (r"massage|care|wellness|relax|spa", "hand-heart"), (r"yoga|meditat|mindful|pilates|breath", "flower-2"),
    (r"health|clinic|doctor|medical|checkup|nurse", "stethoscope"), (r"heart|cardio", "heart-pulse"), (r"pharma|medicine|pill", "pill"),
    (r"dental|teeth|smile|dentist", "smile"), (r"baby|infant|toddler|nursery", "baby"), (r"dog|puppy|groom", "dog"), (r"cat\b|kitten", "cat"),
    (r"pet|animal|vet", "paw-print"), (r"gym|weight|strength|lift|muscle|workout|fitness", "dumbbell"), (r"cycl|bike|spin", "bike"),
    (r"compet|win|trophy|champion|league|award", "trophy"), (r"hiit|cardio|speed|fast|quick|express", "timer"), (r"music|band|concert|dj|song", "music"),
    (r"photo|camera|shoot|portrait", "camera"), (r"art|paint|design|creative|colour|color", "palette"), (r"fashion|cloth|dress|shirt|wear", "shirt"),
    (r"jewel|ring|diamond|gold|gem", "gem"), (r"luxury|premium|vip|exclusive", "crown"), (r"car|auto|vehicle|garage|mechanic", "car"),
    (r"repair|fix|plumb|maintenance|service", "wrench"), (r"build|construct|carpent|joiner", "hammer"), (r"paint|decorat", "paint-roller"),
    (r"electric|power|energy|wiring", "zap"), (r"roof|hard hat|site", "hard-hat"), (r"room|hotel|stay|bed|night", "bed-double"),
    (r"travel|flight|trip|tour|holiday", "plane"), (r"location|address|area|city|town|where|visit|find us|map", "map-pin"),
    (r"hour|open|opening|time|monday|tuesday|weekend|daily|schedule", "clock"), (r"book|booking|appointment|reserv|date|calendar", "calendar-days"),
    (r"phone|call|whatsapp", "phone"), (r"email|mail|newsletter|offer|subscribe", "mail"), (r"chat|message|support|help|contact", "message-circle"),
    (r"deliver|shipping|courier|dispatch|truck", "truck"), (r"shop|store|retail|buy", "shopping-bag"), (r"gift|voucher|present", "gift"),
    (r"discount|sale|deal|offer|percent", "percent"), (r"quality|guarantee|trusted|certified|verified", "badge-check"),
    (r"idea|advice|consult|strategy|plan", "lightbulb"), (r"goal|target|focus|result", "target"), (r"launch|start|startup|rocket", "rocket"),
    (r"web|online|internet|global|world", "globe"), (r"app|mobile|phone app|smartphone", "smartphone"), (r"code|developer|software|api", "code"),
    (r"cloud|hosting|server", "cloud"), (r"privacy|private|lock|password", "lock"), (r"customer|client|member|user", "user-round"),
    (r"review|rating|star|favourite|favorite", "star"), (r"news|blog|article|press", "newspaper"), (r"event|party|festival|wedding", "calendar"),
    (r"product|stock|inventory|package|parcel", "package"), (r"church|worship|faith", "church"), (r"camp|hik|mountain", "mountain"),
]


@lru_cache(maxsize=1)
def _svgs():
    return json.loads((Path(__file__).resolve().parent / "static" / "icons.json").read_text())


def svg(name, size=24, label=None):
    inner = _svgs().get(name)
    if inner is None:
        return ""
    aria = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return (f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"{aria}>{inner}</svg>')


def pick(*texts):
    """Icon name for an item from its title (first) and text, or None."""
    for t in texts:
        low = (t or "").lower()
        for pattern, name in RULES:
            if re.search(rf"\b(?:{pattern})", low):
                return name
    return None
