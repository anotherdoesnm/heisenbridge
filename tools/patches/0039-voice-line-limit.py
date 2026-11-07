# 0039 — let long IRCv3 tagged lines through
#
# python-irc hardcodes a 512 byte cap on outgoing lines:
#
#   File "irc/client.py", line 656, in _prep_message
#       raise MessageTooLong(msg)
#
# An SDP offer in a client tag is several kilobytes, so every offer raised
# MessageTooLong and never reached the server — while small ICE candidates went
# through fine, which made the bridge look healthy. There is no config knob for
# it, so the check is lifted for this connection only: short lines keep the
# original path, long ones skip the cap.
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


LIFT_OLD = """    def rtc_to_irc(self, channel: str, payload: str) -> None:
        if self.conn is None or not self.conn.connected:
            return
"""

LIFT_NEW = '''    def _rtc_lift_line_limit(self) -> None:
        """python-irc caps lines at 512 bytes, IRCv3 tags need far more."""
        conn = self.conn

        if conn is None or getattr(conn, "_rtc_line_limit_lifted", False):
            return

        original = conn._prep_message

        def prep(message: str) -> bytes:
            try:
                return original(message)
            except irc.client.MessageTooLong:
                if "\\n" in message:
                    raise

                return conn.encode(message) + b"\\r\\n"

        conn._prep_message = prep
        conn._rtc_line_limit_lifted = True

    def rtc_to_irc(self, channel: str, payload: str) -> None:
        if self.conn is None or not self.conn.connected:
            return

        self._rtc_lift_line_limit()
'''


def main():
    replace_once(NET, LIFT_OLD, LIFT_NEW, "voice-line-limit")


if __name__ == "__main__":
    main()
