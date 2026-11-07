# 0033 — negotiate draft/chathistory even though we ignore it
#
# Servers that implement draft/chathistory fall back to replaying history as
# ordinary messages when the client did not request the capability, which on
# Parley means a steady stream of fallback traffic. Asking for it costs nothing:
# the bridge simply ignores the CHATHISTORY responses it never sends requests for.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"


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


CAPS_OLD = """            "draft/metadata-2",
            "obsidianirc/voice",
        ]
"""

CAPS_NEW = """            "draft/metadata-2",
            "obsidianirc/voice",
            "draft/chathistory",
        ]
"""


def main():
    replace_once(NET, CAPS_OLD, CAPS_NEW, "chathistory-cap")


if __name__ == "__main__":
    main()
