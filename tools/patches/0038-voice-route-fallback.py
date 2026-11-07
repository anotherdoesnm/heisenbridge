# 0038 — deliver nick-addressed signalling to the session that owns the nick
#
# The SFU answers an offer with a TAGMSG sent to the user's nick, and that reply
# does not always carry a `channel` field. rtc_from_irc() routed strictly by
# channel, so the answer (and any ICE that follows it) was dropped and the call
# never completed.
#
# Fall back to every session on the same network when the channel does not match.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MAIN = "heisenbridge/__main__.py"


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


ROUTE_OLD = """    def rtc_from_irc(self, network_name: str, channel: str, payload: str, nick: str) -> None:
        for session in list(self.rtc_sessions):
            network = session.get("network")
            if network is None or network.name != network_name or session.get("channel") != channel:
                continue

            asyncio.ensure_future(session["ws"].send_json({"action": "signal", "payload": payload, "from": nick}))
"""

ROUTE_NEW = """    def rtc_from_irc(self, network_name: str, channel: str, payload: str, nick: str) -> None:
        sessions = [s for s in list(self.rtc_sessions) if s.get("network") is not None]
        sessions = [s for s in sessions if s["network"].name == network_name]
        matching = [s for s in sessions if s.get("channel") == channel]

        # a reply addressed to our nick carries no channel, so fall back to the
        # whole network rather than dropping the answer on the floor
        for session in matching or sessions:
            asyncio.ensure_future(session["ws"].send_json({"action": "signal", "payload": payload, "from": nick}))
"""


def main():
    replace_once(MAIN, ROUTE_OLD, ROUTE_NEW, "voice-route-fallback")


if __name__ == "__main__":
    main()
