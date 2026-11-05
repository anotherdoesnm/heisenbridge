# 0004 — relay Matrix replies to IRC as the +draft/reply tag
#
# _send_message() already resolves the Matrix event a message replies to, so when
# that event was bridged from IRC we know its msgid and can attach the IRCv3
# +draft/reply tag to the outgoing line. Only the first line of a multi-line
# message carries the tag, and only for PRIVMSG (an emote would need a different
# command).
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


REPLY_OLD = """        if event.content.get_edit():
            messages = await self._process_event_content(event, prefix, reply_to)
"""


REPLY_NEW = """        # IRCv3: a Matrix reply becomes a +draft/reply tag when the target is a bridged IRC message
        reply_msgid = self.event_msgids.get(reply_to.event_id) if reply_to is not None else None

        if reply_msgid is not None and getattr(func, "__name__", "") == "privmsg":
            plain_func = func
            state = {"first": True}

            def func(target, text):
                if state["first"]:
                    state["first"] = False
                    self.network.conn.send_items(f"@+draft/reply={reply_msgid} PRIVMSG", target, ":" + text)
                else:
                    plain_func(target, text)

        if event.content.get_edit():
            messages = await self._process_event_content(event, prefix, reply_to)
"""


def main():
    replace_once(PM, REPLY_OLD, REPLY_NEW, "reply-out")


if __name__ == "__main__":
    main()
