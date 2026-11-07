# 0043 — drop history batches instead of posting them as new messages
#
# Servers with draft/chathistory fall back to replaying history on join for
# clients that do not advertise the capability, so the bridge advertises it
# (patch 0033) and never asks for anything. Some servers send the replay anyway,
# wrapped in a BATCH of type chathistory. on_batch only knows draft/multiline,
# so those PRIVMSGs fell through to on_privmsg and were posted into Matrix as
# brand new messages.
#
# Remember such a batch and drop everything tagged with it. The bridge does not
# backfill history on purpose, so this is the correct outcome either way.
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


BATCH_OLD = """        if ref.startswith("+"):
            if event.arguments and event.arguments[0] in ("draft/multiline", "draft/multiline-concat"):
"""

BATCH_NEW = """        if ref.startswith("+"):
            # history replay is not backfilled into Matrix, drop it wholesale
            if event.arguments and event.arguments[0] == "chathistory":
                self.ignored_batches.add(ref[1:])
                logging.debug(f"Ignoring history batch {ref}")
                return

            if event.arguments and event.arguments[0] in ("draft/multiline", "draft/multiline-concat"):
"""

CLOSE_OLD = """        ref = ref[1:]
        for room in self.rooms.values():
"""

CLOSE_NEW = """        ref = ref[1:]

        if ref in self.ignored_batches:
            self.ignored_batches.discard(ref)
            logging.debug(f"History batch {ref} closed")
            return

        for room in self.rooms.values():
"""

INIT_OLD = """        if self.conn:
            self.conn.close()
            self.conn = None
"""

INIT_NEW = """        if self.conn:
            self.conn.close()
            self.conn = None

        self.ignored_batches = set()
"""

PRIV_OLD = """        # IRCv3 multiline: a message tagged with an open batch belongs to that batch
        for tag in event.tags or []:
            if tag["key"] == "batch" and tag["value"] in self.batches:
                self.batches[tag["value"]].append(event.arguments[0])
                return
"""

PRIV_NEW = """        # IRCv3 multiline: a message tagged with an open batch belongs to that batch
        for tag in event.tags or []:
            if tag["key"] == "batch":
                if tag["value"] in getattr(self.network, "ignored_batches", ()):
                    return

                if tag["value"] in self.batches:
                    self.batches[tag["value"]].append(event.arguments[0])
                    return
"""


def main():
    replace_once(NET, BATCH_OLD, BATCH_NEW, "history-open")
    replace_once(NET, CLOSE_OLD, CLOSE_NEW, "history-close")
    replace_once(NET, INIT_OLD, INIT_NEW, "history-init")
    replace_once(PRIV, PRIV_OLD, PRIV_NEW, "history-drop")


if __name__ == "__main__":
    main()
