# 0009 — parse the capability forms that change nicks: multi-prefix, userhost-in-names, extended-join
#
# With multi-prefix a NAMES entry carries every prefix a user holds (~@+nick)
# instead of just the highest one, and with userhost-in-names it also carries the
# hostmask (nick!user@host). strip_nick() only removed a single prefix, so both
# forms produced bogus puppet ids and bogus member lists.
#
# extended-join adds the account name and realname to the JOIN parameters, which
# is safe here because every JOIN handler keys off event.target (the channel) and
# event.source, never off the extra parameters.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MAIN = "heisenbridge/__main__.py"
CHAN = "heisenbridge/channel_room.py"
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


STRIP_OLD = """        m = re.match(r"^([~&@%\\+!]?)(.+)$", nick)
        if m:
            return (m.group(2), (m.group(1) if len(m.group(1)) > 0 else None))
"""

STRIP_NEW = """        m = re.match(r"^([~&@%\\+!]*)(.+)$", nick)
        if m:
            # multi-prefix lists every prefix a user holds, keep the highest one as the mode
            return (m.group(2), (m.group(1)[0] if len(m.group(1)) > 0 else None))
"""

NAMES_OLD = """        for nick in names:
            nick, mode = self.serv.strip_nick(nick)
"""

NAMES_NEW = """        for nick in names:
            nick, mode = self.serv.strip_nick(nick)
            # userhost-in-names appends !user@host to every entry
            nick = nick.split("!", 1)[0]
"""

CAPS_OLD = """            "account-tag",
            "invite-notify",
            "draft/message-redaction",
        ]
"""

CAPS_NEW = """            "account-tag",
            "invite-notify",
            "draft/message-redaction",
            "multi-prefix",
            "userhost-in-names",
            "extended-join",
        ]
"""


def main():
    replace_once(MAIN, STRIP_OLD, STRIP_NEW, "strip-all-prefixes")
    replace_once(CHAN, NAMES_OLD, NAMES_NEW, "names-strip-hostmask")
    replace_once(NET, CAPS_OLD, CAPS_NEW, "caps-names")


if __name__ == "__main__":
    main()
