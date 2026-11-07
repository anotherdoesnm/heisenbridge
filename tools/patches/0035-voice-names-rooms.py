# 0035 — create a room for voice/stream channels we are already in
#
# obbyircd binds channels to the account, so reconnecting puts us back into `^`/`$`
# channels without sending a JOIN. `on_join` is the only place a ChannelRoom is
# created, so those channels never get a Matrix room (and their text side is lost).
#
# NAMES is the signal we do get: when the server lists a voice/stream channel we
# have no room for, create one.
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


REGISTER_OLD = """                self.conn.add_global_handler("tagmsg", self.on_rtc_tagmsg)
"""

REGISTER_NEW = """                self.conn.add_global_handler("tagmsg", self.on_rtc_tagmsg)
                self.conn.add_global_handler("namreply", self.on_channel_names)
                self.conn.add_global_handler("endofnames", self.on_channel_names)
"""

METHOD_OLD = """    def on_rtc_tagmsg(self, conn, event) -> None:
"""

METHOD_NEW = """    def on_channel_names(self, conn, event) -> None:
        # obby binds channels to the account, so a reconnect does not produce a
        # JOIN for the voice/stream channels we are already in. NAMES is all we get.
        target = (event.target or "").lower()

        if not target.startswith(("^", "$")) or target in self.rooms:
            return

        if event.type == "namreply" and conn.real_nickname not in " ".join(event.arguments).split():
            return

        logging.debug(f"Found existing voice channel {target}, creating a room for it")
        self.rooms[target] = ChannelRoom.create(self, event.target)

    def on_rtc_tagmsg(self, conn, event) -> None:
"""


def main():
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "voice-names-register")
    replace_once(NET, METHOD_OLD, METHOD_NEW, "voice-names-handler")


if __name__ == "__main__":
    main()
