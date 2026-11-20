"""Conservative extractive checks for a question, a proposed answer and the page that was cited.

A supported question supplies an ordered relation with one answer slot. Match that relation
against complete source clauses. Ambiguous values and unsupported paraphrases stay unconfirmed.
"""
import re
from functools import lru_cache

NUMBER = r"[+−-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
TOKEN = re.compile(NUMBER + r"|[^\W_]+|[%$£€:/=<>-]", re.UNICODE)
NUM = r"[+-]?\d+(?:\.\d+)?"
VALUE = r"(?P<value>.+?)"
N = rf"(?P<value>{NUM})"
INFLECT = {"is":"be", "are":"be", "was":"be", "were":"be", "has":"have", "had":"have",
           "did":"do", "does":"do", "paid":"pay", "used":"use", "uses":"use", "weighed":"weigh", "costs":"cost",
           "dispatched":"dispatch", "sent":"send", "gave":"give", "took":"take", "held":"hold", "went":"go"}
MODAL = re.compile(r"\b(if|unless|possibly|might|would|could|perhaps|reportedly|either|or|approximate\w*|"
                   r"estimate\w*|rumou?r\w*|alleg\w*|claim|say|said|formerly|instead|hypothetical|proposed|draft|only if)\b")
NEGATION = re.compile(r"\b(?:do )?(?:not|no|never)\b\s*")
PROPERTIES = {"weight":"weigh", "mass":"weigh", "cost":"cost", "price":"cost", "capacity":"hold"}
LOCATION = r"(?:in|at|on|inside|near|under|from|during) .+"


def words(text):
    items = []
    for token in TOKEN.findall(text.casefold().replace("−", "-").replace("’", "'")):
        if token in ("the", "a", "an"):
            continue
        if re.fullmatch(NUMBER, token):
            token = token.replace(",", "")
        elif token in INFLECT:
            token = INFLECT[token]
        elif token.endswith("ies") and len(token) > 4:
            token = token[:-3]+"y"
        elif len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
            token = token[:-1]
        items.append(token)
    return " ".join(items).replace("at time", "at once")


def clauses(text):
    # Keep conditions attached to their statement. Split enumeration only for an explicit shared existential.
    for sentence in re.split(r"(?<!\d)[.!?]|[.!?](?!\d)|;|\n\s*\n", text):
        line = words(sentence)
        if not line or MODAL.search(line) or re.search(r"\b(?:isn|aren|wasn|weren|didn|doesn|can) t\b", line):
            continue
        title, newline, body = sentence.strip().partition("\n")
        if newline and ":" in title and not title.endswith(":") and title.istitle() and not NEGATION.search(words(title)):
            line = words(body)
        # Apposition after a comma can explain the amount in an otherwise complete clause.
        if re.search(r",\s*(?:half|twice|double)\b", sentence, re.I):
            line = words(sentence.split(",", 1)[0])
        existential = re.fullmatch(r"((?:(?:in|at|on|inside) .+? )?there be )(.+)", line)
        if existential:
            head, body = existential.groups()
            parts = body.split(" and ")
            if all(re.match(NUM+r" ", part) for part in parts):
                for part in parts:
                    yield head + part
                continue
        yield line


@lru_cache(maxsize=256)
def frames(q):
    """Each pattern captures the answer slot. The optional noun licenses a count with or without its unit."""
    out = []
    def add(pattern, noun=""):
        out.append((re.compile(pattern), noun))
    def verb_form(word):
        past = word+"d" if word.endswith("e") else word[:-1]+"ied" if word.endswith("y") else word+"ed"
        return "(?:"+re.escape(word)+"|"+re.escape(past)+")"
    count = re.fullmatch(r"how many (.+?) (be|do|may|can)\b(?: (.+))?", q)
    if count:
        noun, aux, rest = count.groups()
        item = re.escape(noun)
        rest = rest or ""
        if aux == "be":
            tail = re.escape(rest.removeprefix("there ").removesuffix(" there")) if rest != "there" else ""
            add(r"(?:there be )?" + N+" "+item+(" "+tail if tail else ""), noun)
            if tail:
                add(N+" "+item+" be "+tail, noun)
                add(r"(?:there be )?"+N+" "+tail+" "+item, noun)
                if re.fullmatch(LOCATION, rest):
                    add(tail+r" there be "+N+" "+item, noun)
        else:
            parts = rest.split()
            for i in range(1,len(parts)):
                subject, verb, tail = " ".join(parts[:i]), parts[i], " ".join(parts[i+1:])
                modal = aux+" " if aux in ("may","can") else ""
                prefix = re.escape(subject+" "+modal)+verb_form(verb)+" "
                limit = r"(?:up to |at most )?" if modal else ""
                add(prefix+limit+N+" "+item+(" "+re.escape(tail) if tail else ""), noun)
        return out
    much = re.fullmatch(r"how much do (.+)",q)
    if much:
        add(re.escape(much[1])+" "+VALUE)
    attr = re.fullmatch(r"what be (.+)",q)
    if attr:
        name = attr[1]
        add(re.escape(name)+" be "+VALUE)
        qualified = re.fullmatch(r"(.+?) (of|for) (.+)",name)
        if qualified:
            prop, _, subject = qualified.groups()
            add(re.escape(subject+" "+prop)+" be "+VALUE)
            if prop in PROPERTIES:
                add(re.escape(subject+" "+PROPERTIES[prop])+" "+VALUE)
    obj = re.fullmatch(r"(who|what|where|when) do (.+)",q)
    if obj:
        prep = r" (?:in|at|on|from) " if obj[1] in ("where","when") else " "
        subject, _, verb = obj[2].rpartition(" ")
        if subject:
            add(re.escape(subject)+" "+verb_form(verb)+prep+VALUE)
    subj = re.fullmatch(r"who (?!do\b)(.+)|which [\w-]+ (.+)",q)
    if subj:
        predicate = subj[1] or subj[2]
        extra = r"(?: [\w-]+)?" if predicate.endswith((" most"," least")) else ""
        add(VALUE+" "+re.escape(predicate)+extra)
    located = re.fullmatch(r"(?:where|when) be (.+)",q)
    if located:
        add(re.escape(located[1])+r" be (?:in|at|on) "+VALUE)
    return out


def extract(q, text):
    supported, denied = {}, set()
    for line in clauses(text):
        negative = NEGATION.search(line)
        statement = NEGATION.sub("",line) if negative else line
        for pattern, noun in frames(q):
            match = pattern.fullmatch(statement)
            if not match:
                continue
            value = match["value"]
            if len(value.split()) > 12 or re.search(r"\b(and|but|except|without|despite|not|no|never)\b", value):
                continue
            if negative:
                denied.add(value)
                continue
            allowed = supported.setdefault(value,set())
            allowed.update((value,line))
            if noun:
                allowed.update((value+" "+noun,"there be "+value+" "+noun))
            if q.startswith("what be "):
                allowed.add(q[8:]+" be "+value)
    return supported, denied


def quoted_on_page(quote, page):
    collapse = lambda s: " ".join(s.casefold().split())
    literal = collapse(quote)
    return len(literal) > 8 and re.search(r"(?<!\w)"+re.escape(literal)+r"(?!\w)",collapse(page)) is not None


def facts_backed(question, answer, quote, page=None):
    if not all(isinstance(x,str) and x.strip() for x in (question,answer,quote)):
        return False
    if page is not None and not quoted_on_page(quote,page):
        return False
    q, claim = words(question), words(answer)
    quoted, denied = extract(q,quote)
    if len(quoted)!=1:
        return False
    value, allowed = next(iter(quoted.items()))
    if value in denied or claim not in allowed or q.startswith(("how many ","how much ")) and not re.search(NUM,value):
        return False
    if page is None:
        return True
    on_page, contradictions = extract(q,page)
    return set(on_page)=={value} and value not in contradictions


def legacy_identity(row):
    """The exact text and source the original document capability wrote to SQLite."""
    return f'{row["question"]} {row["answer"]} (quote: "{row["quote"][:200]}")', f'{row["doc"]} page {row["page"]}'


def document_proof(row, page_text):
    keys = ("question","answer","quote","doc","page")
    if (not isinstance(row,dict) or not all(isinstance(row.get(k),str) for k in keys[:-1])
            or type(row.get("page")) is not int or row["page"] < 1 or not isinstance(page_text,str)):
        return None
    if facts_backed(row["question"],row["answer"],row["quote"],page_text):
        return {**{k:row[k] for k in keys},"page_text":page_text,"version":1}
    return None


def valid_note(proof, text, source):
    return (isinstance(proof,dict) and proof.get("version")==1 and document_proof(proof,proof.get("page_text")) is not None
            and legacy_identity(proof)==(text,source))
