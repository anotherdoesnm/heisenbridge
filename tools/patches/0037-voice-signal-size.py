# 0037 — log the size of outgoing voice signalling
#
# The widget sends an SDP offer that never gets an answer. The offer travels in an
# IRC client tag and obby caps tag size, so an oversized offer is the prime
# suspect. Log the payload length (and the escaped length) so the next test says
# immediately whether that is the problem.
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


SEND_OLD = """        escaped = payload.replace("\\\\", "\\\\\\\\").replace(";", "\\\\:")
        escaped = escaped.replace(" ", "\\\\s").replace("\\r", "").replace("\\n", "")
        self.conn.send_raw(f"@+obsidianirc/rtc={escaped} TAGMSG {channel}")
"""

SEND_NEW = """        escaped = payload.replace("\\\\", "\\\\\\\\").replace(";", "\\\\:")
        escaped = escaped.replace(" ", "\\\\s").replace("\\r", "").replace("\\n", "")
        logging.info(f"Voice signalling to {channel}: {len(payload)} bytes, {len(escaped)} escaped")
        self.conn.send_raw(f"@+obsidianirc/rtc={escaped} TAGMSG {channel}")
"""


def main():
    replace_once(NET, SEND_OLD, SEND_NEW, "voice-signal-size")


if __name__ == "__main__":
    main()
