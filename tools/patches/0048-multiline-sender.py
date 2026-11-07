# 0048 — multiline messages come from the bridge, not from the user
#
# on_multiline joined the buffered lines and called
#
#   self.send_message(text, fallback_html=...)
#
# without a sender, so the event went out as @heisenbridge instead of the
# puppet of whoever wrote it. The batch only stored the lines, and the nick was
# dropped on the floor when the batch was opened.
#
# Keep the sender (and the msgid/reply tags, which sit on the BATCH line rather
# than on the individual lines) with the batch and send as the right user,
# mirroring what on_privmsg does for single-line messages.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"
PRIV = "heisenbridge/private_room.py"


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


OPEN_OLD = """                target = event.arguments[1].lower() if len(event.arguments) > 1 else None
                room = self.rooms.get(target)
                if room is not None:
                    room.batches[ref[1:]] = []
"""

OPEN_NEW = """                target = event.arguments[1].lower() if len(event.arguments) > 1 else None
                room = self.rooms.get(target)

                if room is not None:
                    # the sender and the message tags live on the opening line
                    msgid = None
                    reply = None

                    for tag in event.tags or []:
                        if tag["key"] == "msgid":
                            msgid = tag["value"]
                        elif tag["key"] == "+draft/reply":
                            reply = tag["value"]

                    room.batches[ref[1:]] = {
                        "nick": event.source.nick,
                        "lines": [],
                        "msgid": msgid,
                        "reply": reply,
                    }
"""

CLOSE_OLD = """        for room in self.rooms.values():
            lines = room.batches.pop(ref, None)
            if lines:
                room.on_multiline(lines)
"""

CLOSE_NEW = """        for room in self.rooms.values():
            batch = room.batches.pop(ref, None)
            if batch and batch["lines"]:
                room.on_multiline(batch)
"""

APPEND_OLD = """                if tag["value"] in self.batches:
                    self.batches[tag["value"]].append(event.arguments[0])
                    return
"""

APPEND_NEW = """                if tag["value"] in self.batches:
                    self.batches[tag["value"]]["lines"].append(event.arguments[0])
                    return
"""

MULTILINE_OLD = """    def on_multiline(self, lines) -> None:
        text = "\\n".join(lines)
        self.send_message(text, fallback_html=f"<b>Multiline message</b>: {html.escape(text)}")
"""

MULTILINE_NEW = """    def on_multiline(self, batch) -> None:
        lines = batch.get("lines") or []
        if not lines:
            return

        text = "\\n".join(lines)
        nick = batch.get("nick")

        if nick is None:
            self.send_message(text, fallback_html=f"<b>Multiline message</b>: {html.escape(text)}")
            return

        irc_user_id = self.serv.irc_user_id(self.network.name, nick)

        # our own message echoed back by the server
        if nick == self.network.conn.real_nickname:
            if self.lazy_members is None:
                self.send_message(f"You said: {text}", fallback_html=f"<b>You said</b>: {html.escape(text)}")
                return

            self.lazy_members[irc_user_id] = nick

        relates_to = None
        reply_event_id = self.msgids.get(batch.get("reply")) if batch.get("reply") else None
        if reply_event_id is not None:
            relates_to = {"m.in_reply_to": {"event_id": reply_event_id}}

        self.send_message(
            text,
            irc_user_id,
            fallback_html=f"<b>Multiline message from {nick}</b>: {html.escape(text)}",
            msgid=batch.get("msgid"),
            relates_to=relates_to,
        )

        asyncio.ensure_future(self.serv.ensure_irc_user_id(self.network.name, nick))
"""


def main():
    replace_once(NET, OPEN_OLD, OPEN_NEW, "multiline-open")
    replace_once(NET, CLOSE_OLD, CLOSE_NEW, "multiline-close")
    replace_once(PRIV, APPEND_OLD, APPEND_NEW, "multiline-append")
    replace_once(PRIV, MULTILINE_OLD, MULTILINE_NEW, "multiline-send")


if __name__ == "__main__":
    main()
