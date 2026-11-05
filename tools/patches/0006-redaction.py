# 0006 — bridge IRCv3 message redaction in both directions
#
# draft/message-redaction redacts a message by sending a TAGMSG carrying the
# +draft/redact tag with the msgid of the target. obbyircd advertises the
# capability, so:
#
#   Matrix -> IRC: a redaction of a message that was bridged from IRC sends the
#   tag, using the msgid we kept for that event.
#
#   IRC -> Matrix: an incoming TAGMSG with +draft/redact redacts the Matrix event
#   that the msgid maps to.
#
# The upstream redaction handler only quarantines media, it never tells IRC.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"
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


TAGMSG_REG_OLD = """                self.conn.add_global_handler("tagmsg", self.on_pass_or_ignore)
"""

TAGMSG_REG_NEW = """                self.conn.add_global_handler("tagmsg", self.on_tagmsg)
"""

TAGMSG_DISPATCH_OLD = """    def on_pass_or_ignore(self, conn, event) -> None:
        pass
"""

TAGMSG_DISPATCH_NEW = """    @ircroom_event()
    def on_tagmsg(self, conn, event) -> None:
        # handled by the room when it knows the msgid, see PrivateRoom.on_tagmsg
        pass

    def on_pass_or_ignore(self, conn, event) -> None:
        pass
"""

REDACT_OLD = """    async def on_mx_redaction(self, event) -> None:
        for media in self.media:
"""

REDACT_NEW = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        for tag in event.tags or []:
            if tag["key"] == "+draft/redact":
                event_id = self.msgids.get(tag["value"])
                if event_id is not None:
                    asyncio.ensure_future(self.az.intent.redact_event(self.id, event_id))

    async def on_mx_redaction(self, event) -> None:
        # IRCv3: ask the server to redact the message we bridged earlier
        msgid = self.event_msgids.get(event.redacts)
        if msgid is not None and self.network is not None and self.network.conn is not None:
            self.network.conn.send_items(f"@+draft/redact={msgid} TAGMSG", self.name)

        for media in self.media:
"""


def main():
    replace_once(NET, TAGMSG_REG_OLD, TAGMSG_REG_NEW, "tagmsg-register")
    replace_once(NET, TAGMSG_DISPATCH_OLD, TAGMSG_DISPATCH_NEW, "tagmsg-dispatch")
    replace_once(PM, REDACT_OLD, REDACT_NEW, "redaction-both-ways")


if __name__ == "__main__":
    main()
