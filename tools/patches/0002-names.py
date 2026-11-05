# 0002 — de-duplicate the NAMES buffer
#
# on_namreply() appends to names_buffer and on_endofnames() consumes it verbatim.
# When several NAMES replies for one channel land in a single burst (the join
# reply plus an explicit NAMES, or a reconnect) the same nick is listed again and
# again, so the member sync notice read "Users with owner (~): mattf, mattf,
# mattf" and over-reported the name count. Membership itself is unaffected.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PATH = "heisenbridge/channel_room.py"


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


NAMES_OLD = """        names = list(self.names_buffer)
        self.names_buffer = []
"""


NAMES_NEW = """        names = list(dict.fromkeys(self.names_buffer))
        self.names_buffer = []
"""


def main():
    replace_once(PATH, NAMES_OLD, NAMES_NEW, "names-dedupe")


if __name__ == "__main__":
    main()
