# 0003 — remember IRC msgid <-> Matrix event id and bridge IRCv3 replies
#
# The +draft/reply tag and draft/message-redaction reference the msgid of another
# message, so the bridge keeps the mapping between an IRC msgid and the Matrix
# event it was relayed to. The map is in-memory and bounded to 512 entries: after
# a restart replies to older messages do not resolve, which is a fair trade for
# not writing account data on every message.
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


MSGID_INIT_OLD = """        self.displaynames = {}
        self.last_messages = defaultdict(str)
"""


MSGID_INIT_NEW = """        self.displaynames = {}
        # IRC msgid <-> Matrix event id, used for replies, redactions and edits
        self.msgids = {}
        self.event_msgids = {}
        self.last_messages = defaultdict(str)
"""


MSGID_SEND_OLD = """    def send_message(
        self, text: str, user_id: Optional[str] = None, formatted=None, fallback_html: Optional[str] = None
    ) -> None:
"""


MSGID_SEND_NEW = """    def send_message(
        self,
        text: str,
        user_id: Optional[str] = None,
        formatted=None,
        fallback_html: Optional[str] = None,
        msgid: Optional[str] = None,
        relates_to: Optional[dict] = None,
    ) -> None:
"""


MSGID_SEND_TAIL_OLD = """                "fallback_html": fallback_html,
            }

        self._queue.enqueue(event)

    # send emote to mx user (may be puppeted)
"""


MSGID_SEND_TAIL_NEW = """                "fallback_html": fallback_html,
            }

        if msgid is not None:
            event["msgid"] = msgid

        if relates_to is not None:
            event["content"]["m.relates_to"] = relates_to

        self._queue.enqueue(event)

    # send emote to mx user (may be puppeted)
"""


MSGID_FLUSH_OLD = """                    intent = self.az.intent.user(event["user_id"]) if event["user_id"] else self.az.intent
                    type = EventType.find(event["type"])
                    await intent.send_message_event(self.id, type, event["content"])
"""


MSGID_FLUSH_NEW = """                    intent = self.az.intent.user(event["user_id"]) if event["user_id"] else self.az.intent
                    type = EventType.find(event["type"])
                    event_id = await intent.send_message_event(self.id, type, event["content"])

                    # keep msgid <-> event id so replies, redactions and edits can reference it
                    msgid = event.get("msgid")
                    if msgid is not None and event_id is not None:
                        self.msgids[msgid] = event_id
                        self.event_msgids[event_id] = msgid

                        while len(self.msgids) > 512:
                            oldest = next(iter(self.msgids))
                            del self.msgids[oldest]
                            for key, value in list(self.event_msgids.items()):
                                if value == oldest:
                                    del self.event_msgids[key]
                                    break
"""


MSGID_RECV_OLD = """        (plain, formatted) = parse_irc_formatting(event.arguments[0], self.pills(), self.network.color)

        # ignore relaymsgs by us
"""


MSGID_RECV_NEW = """        (plain, formatted) = parse_irc_formatting(event.arguments[0], self.pills(), self.network.color)

        # IRCv3: remember the msgid and resolve a reply to the event it points at
        msgid = None
        relates_to = None

        for tag in event.tags or []:
            if tag["key"] == "msgid":
                msgid = tag["value"]
            elif tag["key"] == "+draft/reply":
                reply_event_id = self.msgids.get(tag["value"])
                if reply_event_id is not None:
                    relates_to = {"m.in_reply_to": {"event_id": reply_event_id}}

        # ignore relaymsgs by us
"""


MSGID_SEND_CALL_OLD = """        self.send_message(
            plain,
            irc_user_id,
            formatted=formatted,
            fallback_html=f"<b>Message from {str(event.source)}</b>: {html.escape(plain)}",
        )
"""


MSGID_SEND_CALL_NEW = """        self.send_message(
            plain,
            irc_user_id,
            formatted=formatted,
            fallback_html=f"<b>Message from {str(event.source)}</b>: {html.escape(plain)}",
            msgid=msgid,
            relates_to=relates_to,
        )
"""


def main():
    replace_once(ROOM, MSGID_INIT_OLD, MSGID_INIT_NEW, "msgid-init")
    replace_once(ROOM, MSGID_SEND_OLD, MSGID_SEND_NEW, "send-signature")
    replace_once(ROOM, MSGID_SEND_TAIL_OLD, MSGID_SEND_TAIL_NEW, "send-relations")
    replace_once(ROOM, MSGID_FLUSH_OLD, MSGID_FLUSH_NEW, "msgid-map")
    replace_once(PM, MSGID_RECV_OLD, MSGID_RECV_NEW, "recv-msgid")
    replace_once(PM, MSGID_SEND_CALL_OLD, MSGID_SEND_CALL_NEW, "recv-reply")


if __name__ == "__main__":
    main()
