# 0030 — keep the voice session alive for a minute after the socket drops
#
# Android destroys the WebView when the app goes to the background, the widget's
# WebSocket closes, and the bridge immediately sent `leave` and parted the IRC
# channel — so minimising the client dropped you out of the call.
#
# Wait a minute before tearing the session down, and cancel the timer when a new
# socket binds to the same channel. Reopening the widget within that window just
# continues the call.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MAIN = "heisenbridge/__main__.py"

LINGER_SECONDS = 60


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


INIT_OLD = """        self.rtc_sessions = []
        self.rtc_pending = {}
"""

INIT_NEW = """        self.rtc_sessions = []
        self.rtc_pending = {}
        self.rtc_lingers = {}
"""

BIND_OLD = """        channel = "^" + room.name.lstrip("#!+").lower()
        session.update(network=network, channel=channel)
"""

BIND_NEW = """        channel = "^" + room.name.lstrip("#!+").lower()
        session.update(network=network, channel=channel)

        # a socket that comes back cancels the pending teardown
        linger = self.rtc_lingers.pop((network.name, channel), None)
        if linger is not None:
            linger.cancel()
"""

LINGER_OLD = """    async def voice_ws(self, request: web.Request) -> web.StreamResponse:
"""

LINGER_NEW = """    def rtc_schedule_leave(self, network, channel: str) -> None:
        key = (network.name, channel)
        previous = self.rtc_lingers.pop(key, None)

        if previous is not None:
            previous.cancel()

        self.rtc_lingers[key] = asyncio.ensure_future(self.rtc_linger(network, channel, key))

    async def rtc_linger(self, network, channel: str, key) -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            return

        self.rtc_lingers.pop(key, None)

        for session in self.rtc_sessions:
            bound = session.get("network")
            if bound is network and session.get("channel") == channel:
                return

        logging.info(f"Voice session for {channel} expired, leaving")
        try:
            network.rtc_to_irc(channel, json.dumps({"type": "leave", "channel": channel}))
            if network.conn is not None and network.conn.connected:
                network.conn.part(channel)
        except Exception:
            logging.debug(f"Failed to leave {channel}", exc_info=True)

    async def voice_ws(self, request: web.Request) -> web.StreamResponse:
"""

CLEANUP_OLD = """            network = session.get("network")
            channel = session.get("channel")
            if network is not None and channel is not None:
                try:
                    network.rtc_to_irc(channel, json.dumps({"type": "leave", "channel": channel}))
                except Exception:
                    pass
"""

CLEANUP_NEW = """            network = session.get("network")
            channel = session.get("channel")
            if network is not None and channel is not None:
                self.rtc_schedule_leave(network, channel)
"""


def main():
    replace_once(MAIN, INIT_OLD, INIT_NEW, "voice-linger-state")
    replace_once(MAIN, BIND_OLD, BIND_NEW, "voice-linger-cancel")
    replace_once(MAIN, LINGER_OLD, LINGER_NEW, "voice-linger-methods")
    replace_once(MAIN, CLEANUP_OLD, CLEANUP_NEW, "voice-linger-on-close")


if __name__ == "__main__":
    main()
