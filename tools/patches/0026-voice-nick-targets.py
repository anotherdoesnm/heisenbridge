# 0026 — route voice replies that are addressed to the nick, not the channel
#
# The SFU answers the join with a TAGMSG sent to the user's nick:
#
#   @+obsidianirc/rtc={"type":"joined","channel":"^bots","turn":{...}} :irc.h4ks.com TAGMSG doesnm
#
# 0023 only accepted TAGMSGs whose target was the `^`/`$` channel, so the reply
# with the TURN credentials was dropped and the widget never learned where to
# send media. Accept nick-targeted envelopes too and route them by the `channel`
# field inside the JSON.
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


IMPORT_OLD = """import hashlib
import html
"""

IMPORT_NEW = """import hashlib
import html
import json
"""

METHOD_OLD = """    def on_rtc_tagmsg(self, conn, event) -> None:
        # obby.world/voice: media signalling is JSON in a client tag
        target = (event.target or "").lower()

        if not target.startswith(("^", "$")):
            return

        for tag in event.tags or []:
            if tag["key"] == "+obsidianirc/rtc":
                self.serv.rtc_from_irc(self.name, target, tag["value"], event.source.nick)
                return
"""

METHOD_NEW = """    def on_rtc_tagmsg(self, conn, event) -> None:
        # obby.world/voice: media signalling is JSON in a client tag. The SFU
        # addresses its replies to our nick, so both shapes have to be accepted.
        target = (event.target or "").lower()
        own_nick = (conn.real_nickname or "").lower()

        if target != own_nick and not target.startswith(("^", "$")):
            return

        for tag in event.tags or []:
            if tag["key"] != "+obsidianirc/rtc":
                continue

            try:
                envelope = json.loads(tag["value"])
            except ValueError:
                return

            channel = (envelope.get("channel") or target).lower()
            self.serv.rtc_from_irc(self.name, channel, tag["value"], event.source.nick)
            return
"""


def main():
    replace_once(NET, IMPORT_OLD, IMPORT_NEW, "voice-json-import")
    replace_once(NET, METHOD_OLD, METHOD_NEW, "voice-nick-targets")


if __name__ == "__main__":
    main()
