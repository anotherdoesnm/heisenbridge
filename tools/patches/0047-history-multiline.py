# 0047 — history inside history
#
# Parley replays channel history on join as a `chathistory` batch, and wraps the
# messages that had several lines in a nested `draft/multiline` batch:
#
#   @batch=5938953f1130 BATCH +4f0d2b0669ae draft/multiline #lobby
#   @batch=4f0d2b0669ae PRIVMSG #lobby :...
#
# 0043 dropped the outer batch, but the inner multiline batch was still
# registered, so on_multiline posted the joined text and the replay came back as
# new messages on every reconnect.
#
# Treat a multiline batch opened inside an ignored batch as ignored too, and
# drop TAGMSGs (reactions, typing) that arrive inside history.
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


MULTI_OLD = """            if event.arguments and event.arguments[0] in ("draft/multiline", "draft/multiline-concat"):
                target = event.arguments[1].lower() if len(event.arguments) > 1 else None
"""

MULTI_NEW = """            if event.arguments and event.arguments[0] in ("draft/multiline", "draft/multiline-concat"):
                # a multiline batch opened inside a history replay is history too
                for tag in event.tags or []:
                    if tag["key"] == "batch" and tag["value"] in self.ignored_batches:
                        self.ignored_batches.add(ref[1:])
                        logging.debug(f"Ignoring multiline batch {ref} inside a history replay")
                        return

                target = event.arguments[1].lower() if len(event.arguments) > 1 else None
"""

TAGMSG_OLD = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        target = None
"""

TAGMSG_NEW = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        # reactions and typing inside a history replay are history as well
        for tag in event.tags or []:
            if tag["key"] == "batch" and tag["value"] in getattr(self.network, "ignored_batches", ()):
                return

        target = None
"""


def main():
    replace_once(NET, MULTI_OLD, MULTI_NEW, "history-multiline")
    replace_once(PRIV, TAGMSG_OLD, TAGMSG_NEW, "history-tagmsg")


if __name__ == "__main__":
    main()
