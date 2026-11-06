# 0022 — typing indicators from IRC (IRCv3 +typing client tag)
#
# The `typing` client tag is a client-only tag on TAGMSG:
#
#   @+typing=active :nick!user@host TAGMSG #channel
#
# It only needs `message-tags`, which the bridge already negotiates, and servers
# such as obbyircd relay it. Map it onto Matrix typing notifications:
#
#   IRC  +typing=active/paused/done  ->  m.typing (6s / 6s / 0s)
#
# The other direction is not possible: Matrix does not deliver ephemeral events
# (m.typing, m.receipt) to appservices, so the bridge never learns that its user
# started typing and cannot forward it to IRC.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PM = "heisenbridge/private_room.py"


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


TAGMSG_OLD = """        target = None
        redact = None
        react = None

        for tag in event.tags or []:
            if tag["key"] == "+draft/reply":
                target = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/redact":
                redact = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/react":
                react = tag["value"]

        if redact is not None:
"""

TAGMSG_NEW = """        target = None
        redact = None
        react = None
        typing = None

        for tag in event.tags or []:
            if tag["key"] == "+draft/reply":
                target = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/redact":
                redact = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/react":
                react = tag["value"]
            elif tag["key"] == "+typing":
                typing = tag["value"]

        if typing is not None:
            irc_user_id = self.serv.irc_user_id(self.network.name, event.source.nick)
            # active and paused both keep the indicator alive, done clears it
            timeout = 0 if typing == "done" else 6000
            asyncio.ensure_future(self.az.intent.user(irc_user_id).set_typing(self.id, timeout))

        if redact is not None:
"""


def main():
    replace_once(PM, TAGMSG_OLD, TAGMSG_NEW, "typing-incoming")


if __name__ == "__main__":
    main()
