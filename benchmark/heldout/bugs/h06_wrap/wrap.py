"""Word wrapping."""


def wrap(text, width):
    """Split text into lines of at most `width` characters, breaking only at spaces.
    A single word longer than `width` gets a line of its own."""
    lines = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def longest_line(lines):
    return max((len(l) for l in lines), default=0)
