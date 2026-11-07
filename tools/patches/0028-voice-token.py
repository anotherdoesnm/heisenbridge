# 0028 — bind the voice widget with a token instead of the widget API
#
# On Android the widget runs inside a WebView iframe and Commet's JS bridge never
# answered any request — even `request_capabilities` timed out, so the widget
# could not send the handshake message and the socket stayed unbound.
#
# Drop the widget API entirely: the bridge writes a token into the widget URL when
# it creates the state event, and the socket handshake presents it. The token is
# an HMAC of the room id keyed with `media_key`, so nothing has to be stored and
# it stays valid across restarts. Only the bridge can compute it, which is enough
# because the URL itself is already visible to room members.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ROOM = "heisenbridge/room.py"
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


URL_OLD = """        url = f"{base.rstrip('/')}/voice/index.html?roomId={self.id}"
"""

URL_NEW = """        token = self.serv.rtc_token(self.id)
        url = f"{base.rstrip('/')}/voice/index.html?roomId={self.id}&token={token}"
"""

HANDSHAKE_OLD = """                if action == "handshake":
                    nonce = data.get("nonce")
                    if nonce:
                        self.rtc_pending[nonce] = session
                        logging.debug(f"Voice handshake waiting for nonce {nonce}")
                    continue
"""

HANDSHAKE_NEW = """                if action == "handshake":
                    room_id = data.get("room_id")
                    token = data.get("token")

                    if room_id and token and self.rtc_token(room_id) == token:
                        self.rtc_bind_room(session, room_id)
                    else:
                        await ws.send_json({"action": "error", "message": "bad voice token"})
                    continue
"""

METHODS_OLD = """    def rtc_bind(self, nonce: str, sender: str, room_id: str) -> None:
"""

METHODS_NEW = """    def rtc_token(self, room_id: str) -> str:
        # only the bridge can derive this, and it needs no storage
        return hmac.new(self.media_key, room_id.encode(), hashlib.sha256).hexdigest()[:32]

    def rtc_bind_room(self, session, room_id: str) -> None:
        room = self._rooms.get(room_id)
        network = getattr(room, "network", None) if room is not None else None

        if network is None:
            logging.debug(f"Voice handshake for {room_id} has no network room")
            return

        channel = "^" + room.name.lstrip("#!+").lower()
        session.update(network=network, channel=channel)

        nick = network.conn.real_nickname if network.conn is not None else None
        asyncio.ensure_future(
            session["ws"].send_json({"action": "ready", "network": network.name, "channel": channel, "nick": nick})
        )
        logging.info(f"Voice session bound to {room_id} on {network.name} {channel}")

    def rtc_bind(self, nonce: str, sender: str, room_id: str) -> None:
"""


def main():
    replace_once(ROOM, URL_OLD, URL_NEW, "voice-widget-token-url")
    replace_once(MAIN, HANDSHAKE_OLD, HANDSHAKE_NEW, "voice-token-handshake")
    replace_once(MAIN, METHODS_OLD, METHODS_NEW, "voice-token-methods")


if __name__ == "__main__":
    main()
