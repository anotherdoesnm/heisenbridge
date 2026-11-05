# 0005 — never merge a message that carries a relation
#
# The event queue merges consecutive messages from the same sender into one
# Matrix event. That is fine for plain lines, but a reply (or a reaction, or an
# edit) carries m.relates_to, and merging it into the previous message both
# loses the relation and corrupts the body. Such events now flush on their own.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
QUEUE = "heisenbridge/event_queue.py"


def replace_once(path, old, new, label):
    file = ROOT / path
    text = file.read_text()

    if new in text:
        print(f"{label}: already applied")
        return

    if old not in text:
        sys.exit(f"{label}: anchor not found in {path}, update this patch")

    file.write_text(text.replace(old, new, 1))
    print(f"{label}: patched {path}")


MERGE_OLD = """                and prev_formatted == cur_formatted
                and prev_len < 64_000  # a single IRC event can't overflow with this
            ):
"""


MERGE_NEW = """                and prev_formatted == cur_formatted
                and prev_len < 64_000  # a single IRC event can't overflow with this
                and "m.relates_to" not in prev["content"]
                and "m.relates_to" not in event["content"]
            ):
"""


def main():
    replace_once(QUEUE, MERGE_OLD, MERGE_NEW, "no-merge-relations")


if __name__ == "__main__":
    main()
