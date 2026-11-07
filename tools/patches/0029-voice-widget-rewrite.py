# 0029 — always rewrite the voice widget state
#
# 0027 skipped the state event when one already existed, which left the rooms that
# got the first version with a widget URL without a token (0028). Writing the
# state event again is cheap and makes the URL self-healing after a change.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ROOM = "heisenbridge/room.py"


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


STATE_OLD = """        widget_id = "irc-voice"

        try:
            await self.az.intent.get_state_event(self.id, "im.vector.modular.widgets", widget_id)
            return
        except Exception:
            pass

        token = self.serv.rtc_token(self.id)
"""

STATE_NEW = """        widget_id = "irc-voice"
        token = self.serv.rtc_token(self.id)
"""


def main():
    replace_once(ROOM, STATE_OLD, STATE_NEW, "voice-widget-always-write")


if __name__ == "__main__":
    main()
