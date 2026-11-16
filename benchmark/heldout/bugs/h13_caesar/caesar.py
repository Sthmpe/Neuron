"""The Caesar cipher: shift every letter along the alphabet."""


def shift_char(ch, shift):
    if ch.islower():
        return chr((ord(ch) - ord("a") + shift) % 26 + ord("a"))
    if ch.isupper():
        return chr((ord(ch) - ord("a") + shift) % 26 + ord("A"))
    return ch


def encrypt(text, shift):
    return "".join(shift_char(c, shift) for c in text)


def decrypt(text, shift):
    return encrypt(text, -shift)
