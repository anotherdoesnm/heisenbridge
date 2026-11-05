# 0011 — draft/multiline: send and receive multi-line messages as IRCv3 batches
#
# Outgoing: a Matrix message that spans several lines is sent as one BATCH with
# the draft/multiline-concat type instead of a burst of PRIVMSGs, so other
# clients show it as a single message.
#
# Incoming: PRIVMSGs tagged with an open batch are collected and handed to the
# room when the BATCH closes, which becomes one Matrix event with newlines.
#
# Both directions only act when the server actually negotiated draft/multiline.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ROOM = "heisenbridge/room.py"
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


INIT_OLD = """        self.msgids = {}
        self.event_msgids = {}
"""

INIT_NEW = """        self.msgids = {}
        self.event_msgids = {}
        # open draft/multiline batches, keyed by batch reference
        self.batches = {}
"""

REGISTER_OLD = """                self.conn.add_global_handler("tagmsg", self.on_tagmsg)
"""

REGISTER_NEW = """                self.conn.add_global_handler("tagmsg", self.on_tagmsg)
                self.conn.add_global_handler("batch", self.on_batch)
"""

BATCH_OLD = """    @ircroom_event()
    def on_tagmsg(self, conn, event) -> None:
"""

BATCH_NEW = """    def on_batch(self, conn, event) -> None:
        ref = event.target
        if not ref:
            return

        if ref.startswith("+"):
            if event.arguments and event.arguments[0] == "draft/multiline-concat":
                target = event.arguments[1].lower() if len(event.arguments) > 1 else None
                room = self.rooms.get(target)
                if room is not None:
                    room.batches[ref[1:]] = []
            return

        if not ref.startswith("-"):
            return

        ref = ref[1:]
        for room in self.rooms.values():
            lines = room.batches.pop(ref, None)
            if lines:
                room.on_multiline(lines)

    @ircroom_event()
    def on_tagmsg(self, conn, event) -> None:
"""

RECV_OLD = """        (plain, formatted) = parse_irc_formatting(event.arguments[0], self.pills(), self.network.color)

        # IRCv3: remember the msgid and resolve a reply to the event it points at
"""

RECV_NEW = """        # IRCv3 multiline: a message tagged with an open batch belongs to that batch
        for tag in event.tags or []:
            if tag["key"] == "batch" and tag["value"] in self.batches:
                self.batches[tag["value"]].append(event.arguments[0])
                return

        (plain, formatted) = parse_irc_formatting(event.arguments[0], self.pills(), self.network.color)

        # IRCv3: remember the msgid and resolve a reply to the event it points at
"""

MULTILINE_OLD = """    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        target = None
"""

MULTILINE_NEW = """    def on_multiline(self, lines) -> None:
        text = "\\n".join(lines)
        self.send_message(text, fallback_html=f"<b>Multiline message</b>: {html.escape(text)}")

    def on_tagmsg(self, conn, event) -> None:
        if self.network is None:
            return

        target = None
"""

SEND_OLD = """        for i, message in enumerate(messages):
"""

SEND_NEW = """        if len(messages) > 1 and "draft/multiline" in (self.network.caps_enabled or []):
            ref = f"ml{int(asyncio.get_running_loop().time() * 1000)}"
            self.network.conn.send_items("BATCH", f"+{ref}", "draft/multiline-concat", self.name)
            for message in messages:
                self.network.conn.send_items(f"@batch={ref} PRIVMSG", self.name, ":" + message)
            self.network.conn.send_items("BATCH", f"-{ref}")
            return

        for i, message in enumerate(messages):
"""

CAPS_OLD = """            "extended-join",
            "away-notify",
        ]
"""

CAPS_NEW = """            "extended-join",
            "away-notify",
            "draft/multiline",
        ]
"""


def main():
    replace_once(ROOM, INIT_OLD, INIT_NEW, "batches-state")
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "batch-register")
    replace_once(NET, BATCH_OLD, BATCH_NEW, "batch-handler")
    replace_once(PM, RECV_OLD, RECV_NEW, "batch-recv")
    replace_once(PM, MULTILINE_OLD, MULTILINE_NEW, "multiline-method")
    replace_once(PM, SEND_OLD, SEND_NEW, "batch-send")
    replace_once(NET, CAPS_OLD, CAPS_NEW, "caps-multiline")


if __name__ == "__main__":
    main()
