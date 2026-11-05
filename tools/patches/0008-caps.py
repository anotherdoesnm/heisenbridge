# 0008 — request the IRCv3 capabilities the bridge now understands
#
# account-tag and invite-notify only add information to existing events, and
# draft/message-redaction is what makes the server deliver +draft/redact TAGMSGs
# to us at all (without it the redaction handler never fires).
#
# Capabilities that change the shape of existing messages (extended-join,
# multi-prefix, userhost-in-names, draft/multiline, read-marker) are deliberately
# left out here: each one needs its own parsing patch, and enabling it first
# would corrupt names and joins.
#
# Existing network rooms have their capability list persisted in account data,
# so the defaults are unioned in on load instead of replacing the stored list.
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


CAPS_OLD = """        self.caps = ["message-tags", "chghost", "znc.in/self-message"]
"""

CAPS_NEW = """        self.caps = [
            "message-tags",
            "chghost",
            "znc.in/self-message",
            "account-tag",
            "invite-notify",
            "draft/message-redaction",
        ]
"""

LOAD_OLD = """        if "caps" in config:
            self.caps = config["caps"]
"""

LOAD_NEW = """        if "caps" in config:
            # union with the defaults so capabilities added by a new bridge version
            # reach networks that already have their list stored in account data
            self.caps = sorted(set(config["caps"]) | set(self.caps))
"""


def main():
    replace_once(NET, CAPS_OLD, CAPS_NEW, "default-caps")
    replace_once(NET, LOAD_OLD, LOAD_NEW, "merge-caps")


if __name__ == "__main__":
    main()
