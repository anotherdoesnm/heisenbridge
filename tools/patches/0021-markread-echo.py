# 0021 — do not echo MARKREAD back into the room
#
# With draft/read-marker the bridge tells the server which message the user has
# read:
#
#   MARKREAD #channel timestamp=2026-11-06T07:01:04.052Z
#
# The server mirrors that line back to every client of the connection, and
# heisenbridge has no handler for it, so it falls through to on_server_message and
# shows up as a notice in the network room:
#
#   timestamp=2026-11-06T07:01:04.052Z
#
# Swallow the echo; it carries nothing the user needs.
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


REGISTER_OLD = """                self.conn.add_global_handler("away", self.on_away)
"""

REGISTER_NEW = """                self.conn.add_global_handler("away", self.on_away)
                self.conn.add_global_handler("markread", self.on_markread)
"""

METHOD_OLD = """    def on_away(self, conn, event) -> None:
"""

METHOD_NEW = """    def on_markread(self, conn, event) -> None:
        # draft/read-marker: the server echoes our own MARKREAD back, and there is
        # nothing useful to show for it
        logging.debug(f"Read marker for {event.target}: {' '.join(event.arguments)}")

    def on_away(self, conn, event) -> None:
"""


def main():
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "markread-register")
    replace_once(NET, METHOD_OLD, METHOD_NEW, "markread-handler")


if __name__ == "__main__":
    main()
