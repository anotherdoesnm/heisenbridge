# 0014 — draft/read-marker: tell IRC how far the Matrix side has read
#
# The bridge already sends a Matrix read receipt when the user posts in a room;
# with draft/read-marker the same moment is reported to the network as
# "MARKREAD <target> timestamp=<iso8601>", so IRC clients that show read markers
# stay in sync.
#
# The reverse direction is not bridged: a read marker from another IRC user
# describes *their* read state, and a Matrix receipt cannot be written on behalf
# of another user.
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


RECEIPT_OLD = """        await self.az.intent.send_receipt(event.room_id, event.event_id)
"""

RECEIPT_NEW = """        await self.az.intent.send_receipt(event.room_id, event.event_id)

        # IRCv3 read markers: report the same moment to the network
        if (
            self.network is not None
            and self.network.conn is not None
            and "draft/read-marker" in (self.network.caps_enabled or [])
        ):
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            self.network.conn.send_items("MARKREAD", self.name, f"timestamp={stamp}")
"""

CAPS_OLD = """            "draft/multiline",
            "standard-replies",
        ]
"""

CAPS_NEW = """            "draft/multiline",
            "standard-replies",
            "draft/read-marker",
        ]
"""


def main():
    replace_once(PM, RECEIPT_OLD, RECEIPT_NEW, "read-marker-send")
    replace_once(NET, CAPS_OLD, CAPS_NEW, "caps-read-marker")


if __name__ == "__main__":
    main()
