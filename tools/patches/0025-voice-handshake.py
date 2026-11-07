# 0025 — hand the voice widget a message based handshake
#
# The bridge creates its channel rooms with the user at power level 0, so the
# widget's state event (`com.obby.rtc.session`) was rejected with
#
#   M_FORBIDDEN: sender does not have enough power for com.obby.rtc.session
#
# and the socket never bound. Use a plain message instead: users can always send
# those, and the bridge swallows and redacts it before anything reaches IRC.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MAIN = "heisenbridge/__main__.py"


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


EVENT_OLD = """        # the voice widget proves who it is by writing a nonce into the room
        if str(event.type) == "com.obby.rtc.session":
            nonce = (event.content or {}).get("nonce")
            if nonce:
                self.rtc_bind(nonce, event.sender, event.room_id)
            return
"""

EVENT_NEW = """        # the voice widget proves who it is by posting a nonce into the room. A
        # message is used because the bridge's channel rooms leave the user at
        # power level 0, which is not enough for a state event.
        if str(event.type) == "m.room.message":
            body = getattr(event.content, "body", "") or ""
            if body.startswith("!obby-voice-handshake "):
                nonce = body.split(" ", 1)[1].strip()
                if nonce:
                    self.rtc_bind(nonce, event.sender, event.room_id)
                    asyncio.ensure_future(self.az.intent.redact(event.room_id, event.event_id))
                return
"""


def main():
    replace_once(MAIN, EVENT_OLD, EVENT_NEW, "voice-handshake-message")


if __name__ == "__main__":
    main()
