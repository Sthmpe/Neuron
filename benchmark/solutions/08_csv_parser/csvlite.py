"""A minimal CSV line parser (no external libraries)."""


def parse_line(line, delimiter=","):
    """Split one CSV line into fields. Fields may be wrapped in double quotes;
    inside quotes a delimiter is ordinary text and "" means one quote character."""
    fields = []
    current = ""
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    current += '"'
                    i += 1
                else:
                    in_quotes = False
            else:
                current += ch
        elif ch == '"':
            in_quotes = True
        elif ch == delimiter:
            fields.append(current)
            current = ""
        else:
            current += ch
        i += 1
    fields.append(current)
    return fields


def parse(text, delimiter=","):
    """Parse several lines into a list of dicts keyed by the header row."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    header = parse_line(lines[0], delimiter)
    return [dict(zip(header, parse_line(l, delimiter))) for l in lines[1:]]
