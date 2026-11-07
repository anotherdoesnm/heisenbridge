# 0042 — the last two reconnect leftovers
#
# 1. Every join makes the server send NAMES, and on_endofnames posts a
#    "Synchronizing members: got N from server, ..." summary. On a reconnect the
#    member list has not changed, so the summary is noise — swallow it in the
#    same quiet window as the rest of the join burst.
#
# 2. Voice signalling was sent to the channel even after the widget had left it,
#    so the server answered "No such nick/channel" and the bridge posted that
#    into the network room. Drop signalling for channels we are not in.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHAN = "heisenbridge/channel_room.py"
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


SYNC_OLD = """        self.send_notice(
            "Synchronizing members:"
            + f" got {len(names)} from server,"
            + f" {len(self.members)} in room,"
            + f" {len(to_add)} will be invited and {len(to_remove)} removed."
        )
"""

SYNC_NEW = """        if not self._quiet():
            self.send_notice(
                "Synchronizing members:"
                + f" got {len(names)} from server,"
                + f" {len(self.members)} in room,"
                + f" {len(to_add)} will be invited and {len(to_remove)} removed."
            )
"""

RTC_OLD = """        self._rtc_lift_line_limit()
"""

RTC_NEW = """        self._rtc_lift_line_limit()

        room = self.rooms.get(channel.lower())

        if room is not None and room.on_channel and self.conn.real_nickname.lower() not in room.on_channel:
            logging.debug(f"Not in {channel}, dropping voice signalling")
            return
"""


def main():
    replace_once(CHAN, SYNC_OLD, SYNC_NEW, "quiet-sync")
    replace_once(NET, RTC_OLD, RTC_NEW, "rtc-membership")


if __name__ == "__main__":
    main()
