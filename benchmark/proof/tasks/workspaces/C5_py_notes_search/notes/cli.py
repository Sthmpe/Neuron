import os
import sys

from . import store

FILE = os.environ.get("NOTES_FILE", "notes.json")


def main(argv):
    if argv[:1] == ["add"] and len(argv) == 3:
        store.add(FILE, argv[1], argv[2])
        print("added")
    elif argv[:1] == ["list"]:
        for n in store.load(FILE):
            print(n["title"])
    else:
        print("usage: add TITLE BODY | list")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
