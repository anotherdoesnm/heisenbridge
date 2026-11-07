# 0039 — let long IRCv3 tagged lines through
#
# python-irc refuses to send a line longer than 512 bytes:
#
#   File "irc/client.py", line 656, in _prep_message
#       raise MessageTooLong(msg)
#
# An SDP offer in a client tag is several kilobytes, so every offer raised
# MessageTooLong and never reached the server — while small ICE candidates went
# through fine, which made the bridge look healthy. Raise the limit to the size
# servers actually allow for tagged messages.
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


SEND_OLD = """    def rtc_to_irc(self, channel: str, payload: str) -> None:
        if self.conn is None or not self.conn.connected:
            return
"""

SEND_NEW = """    def rtc_to_irc(self, channel: str, payload: str) -> None:
        if self.conn is None or not self.conn.connected:
            return

        # python-irc caps lines at 512 bytes, but IRCv3 tags allow far more and
        # media signalling needs it
        if self.conn.max_line_length is not None and self.conn.max_line_length < 8192:
            self.conn.max_line_length = 8192
"""


def main():
    replace_once(NET, SEND_OLD, SEND_NEW, "voice-line-limit")


if __name__ == "__main__":
    main()
