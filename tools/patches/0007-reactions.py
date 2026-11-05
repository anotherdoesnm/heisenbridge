# 0007 — bridge IRCv3 reactions in both directions
#
# draft/reactions sends a reaction as a TAGMSG carrying +draft/react=<reaction>
# and +draft/reply=<msgid of the reacted message>. obbyircd advertises
# draft/message-redaction and message-tags, so the tags travel.
#
#   Matrix -> IRC: an m.reaction on a bridged message becomes the TAGMSG above.
#   IRC -> Matrix: a TAGMSG with +draft/react becomes an m.reaction annotation
#   from the puppet that sent it.
#
# Un-reacting (+draft/unreact) is not bridged yet: removing an annotation means
# redacting the reaction event, which needs a reaction -> event map we do not
# keep. It is left out rather than half-working.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ROOM = "heisenbridge/room.py"
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


REACT_OLD = """    def react(self, event_id: str, text: str) -> None:
        event = {
            "type": "m.reaction",
            "content": {
                "m.relates_to": {
                    "event_id": event_id,
                    "key": text,
                    "rel_type": "m.annotation",
                }
            },
            "user_id": None,
        }

        self._queue.enqueue(event)
"""

REACT_NEW = """    def react(self, event_id: str, text: str, user_id: Optional[str] = None) -> None:
        event = {
            "type": "m.reaction",
            "content": {
                "m.relates_to": {
                    "event_id": event_id,
                    "key": text,
                    "rel_type": "m.annotation",
                }
            },
            "user_id": user_id,
        }

        self._queue.enqueue(event)
"""

TAGMSG_OLD = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        for tag in event.tags or []:
            if tag["key"] == "+draft/redact":
                event_id = self.msgids.get(tag["value"])
                if event_id is not None:
                    asyncio.ensure_future(self.az.intent.redact_event(self.id, event_id))
"""

TAGMSG_NEW = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        target = None
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
            asyncio.ensure_future(self.az.intent.redact_event(self.id, redact))

        if react is not None and target is not None:
            irc_user_id = self.serv.irc_user_id(self.network.name, event.source.nick)
            self.react(target, react, irc_user_id)
"""

REGISTER_OLD = """        self.mx_register("m.room.redaction", self.on_mx_redaction)
"""

REGISTER_NEW = """        self.mx_register("m.room.redaction", self.on_mx_redaction)
        self.mx_register("m.reaction", self.on_mx_reaction)
"""

MX_REACT_OLD = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return
"""

MX_REACT_NEW = """    async def on_mx_reaction(self, event) -> None:
        if self.network is None or self.network.conn is None or not self.network.conn.connected:
            return

        relates_to = event.content.relates_to
        if relates_to is None or relates_to.rel_type != "m.annotation":
            return

        msgid = self.event_msgids.get(relates_to.event_id)
        if msgid is None:
            return

        self.network.conn.send_items(f"@+draft/react={relates_to.key};+draft/reply={msgid} TAGMSG", self.name)

    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return
"""


def main():
    replace_once(ROOM, REACT_OLD, REACT_NEW, "react-user-id")
    replace_once(PM, TAGMSG_OLD, TAGMSG_NEW, "tagmsg-reactions")
    replace_once(PM, REGISTER_OLD, REGISTER_NEW, "register-mx-reaction")
    replace_once(PM, MX_REACT_OLD, MX_REACT_NEW, "mx-reaction-to-irc")


if __name__ == "__main__":
    main()
