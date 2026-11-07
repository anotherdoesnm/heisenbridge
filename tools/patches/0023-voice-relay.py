# 0023 — relay obby.world/voice channels to a Matrix widget
#
# obby's voice channels are IRC channels with the `^` prefix (streams use `$`).
# Joining one requires the `obsidianirc/voice` client capability, and all media
# signalling is JSON in a client tag:
#
#   @+obsidianirc/rtc={"type":"join","channel":"^bots"} TAGMSG ^bots
#   <- {"type":"joined","turn":{...},"mode":"voice","role":"streamer",...}
#
# The bridge does not touch the media at all: it only relays those envelopes
# between the IRC connection and a WebSocket that the Matrix widget opens. The
# widget does WebRTC against the SFU the server points at, so a Matrix user
# appears in the IRC channel as a normal participant.
#
# Handshake: the widget opens the socket, sends a nonce and writes the same
# nonce into a `com.obby.rtc.session` state event in the room. Seeing that event
# from the real user binds the socket to their IRC connection, so no extra
# credentials are needed and a room id alone is not enough to impersonate anyone.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"
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


CAPS_OLD = """            "batch",
            "draft/metadata-2",
        ]
"""

CAPS_NEW = """            "batch",
            "draft/metadata-2",
            "obsidianirc/voice",
        ]
"""

REGISTER_OLD = """                self.conn.add_global_handler("batch", self.on_batch)
"""

REGISTER_NEW = """                self.conn.add_global_handler("batch", self.on_batch)
                self.conn.add_global_handler("tagmsg", self.on_rtc_tagmsg)
"""

JOIN_OLD = """        if event.source.nick == self.conn.real_nickname and target not in self.rooms:
            logging.debug("Pre-flight check for JOIN ok, going to create it...")
"""

JOIN_NEW = """        if event.source.nick == self.conn.real_nickname and target not in self.rooms:
            # voice (`^`) and stream (`$`) channels carry no text, the widget
            # talks to the SFU directly and there is nothing to bridge into a room
            if target.startswith(("^", "$")):
                logging.debug(f"Joined voice channel {target}, no Matrix room needed")
                return

            logging.debug("Pre-flight check for JOIN ok, going to create it...")
"""

METHODS_OLD = """    def on_markread(self, conn, event) -> None:
"""

METHODS_NEW = """    def on_rtc_tagmsg(self, conn, event) -> None:
        # obby.world/voice: media signalling is JSON in a client tag
        target = (event.target or "").lower()

        if not target.startswith(("^", "$")):
            return

        for tag in event.tags or []:
            if tag["key"] == "+obsidianirc/rtc":
                self.serv.rtc_from_irc(self.name, target, tag["value"], event.source.nick)
                return

    def rtc_to_irc(self, channel: str, payload: str) -> None:
        if self.conn is None or not self.conn.connected:
            return

        # IRCv3 tag escaping: backslash, semicolon, space, CR and LF
        escaped = payload.replace("\\\\", "\\\\\\\\").replace(";", "\\\\:")
        escaped = escaped.replace(" ", "\\\\s").replace("\\r", "").replace("\\n", "")
        self.conn.send_raw(f"@+obsidianirc/rtc={escaped} TAGMSG {channel}")

    def on_markread(self, conn, event) -> None:
"""

IMPORT_OLD = """import hmac
import logging
"""

IMPORT_NEW = """import hmac
import json
import logging
"""

PATHLIB_OLD = """import os
import pwd
"""

PATHLIB_NEW = """import os
import pathlib
import pwd
"""

INIT_OLD = """        self._rooms = {}
        self._users = {}
"""

INIT_NEW = """        self._rooms = {}
        self._users = {}
        # voice widget sessions: {"ws", "network", "channel", "user"}
        self.rtc_sessions = []
        self.rtc_pending = {}
"""

ROUTES_OLD = """        self.az.app.router.add_get("/_heisenbridge/media/{server}/{media_id}/{checksum}", self.proxy_media)
"""

ROUTES_NEW = """        self.az.app.router.add_get("/_heisenbridge/media/{server}/{media_id}/{checksum}", self.proxy_media)
        self.az.app.router.add_get("/voice/ws", self.voice_ws)
        self.az.app.router.add_static("/voice", pathlib.Path(__file__).resolve().parent.parent / "voice")
"""

EVENT_OLD = """    async def _on_mx_event(self, event):
        if event.room_id and event.room_id in self._rooms:
"""

EVENT_NEW = """    async def _on_mx_event(self, event):
        # the voice widget proves who it is by writing a nonce into the room
        if str(event.type) == "com.obby.rtc.session":
            nonce = (event.content or {}).get("nonce")
            if nonce:
                self.rtc_bind(nonce, event.sender, event.room_id)
            return

        if event.room_id and event.room_id in self._rooms:
"""

VOICE_OLD = """    async def detect_public_endpoint(self):
"""

VOICE_NEW = """    def rtc_bind(self, nonce: str, sender: str, room_id: str) -> None:
        session = self.rtc_pending.pop(nonce, None)
        if session is None:
            return

        room = self._rooms.get(room_id)
        network = getattr(room, "network", None) if room is not None else None
        if network is None:
            logging.debug(f"Voice handshake for {room_id} has no network room")
            return

        channel = "^" + room.name.lstrip("#!+").lower()
        session.update(network=network, channel=channel, user=sender)

        nick = network.conn.real_nickname if network.conn is not None else None
        asyncio.ensure_future(
            session["ws"].send_json({"action": "ready", "network": network.name, "channel": channel, "nick": nick})
        )
        logging.info(f"Voice session bound to {sender} on {network.name} {channel}")

    def rtc_from_irc(self, network_name: str, channel: str, payload: str, nick: str) -> None:
        for session in list(self.rtc_sessions):
            network = session.get("network")
            if network is None or network.name != network_name or session.get("channel") != channel:
                continue

            asyncio.ensure_future(session["ws"].send_json({"action": "signal", "payload": payload, "from": nick}))

    async def voice_ws(self, request: web.Request) -> web.StreamResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        session = {"ws": ws, "network": None, "channel": None, "user": None}
        self.rtc_sessions.append(session)

        try:
            async for message in ws:
                if message.type != web.WSMsgType.TEXT:
                    continue

                try:
                    data = json.loads(message.data)
                except ValueError:
                    continue

                action = data.get("action")

                if action == "handshake":
                    nonce = data.get("nonce")
                    if nonce:
                        self.rtc_pending[nonce] = session
                        logging.debug(f"Voice handshake waiting for nonce {nonce}")
                    continue

                network = session.get("network")
                channel = session.get("channel")

                if network is None or channel is None:
                    await ws.send_json({"action": "error", "message": "not bound to a room yet"})
                    continue

                if action == "join":
                    if network.conn is not None and network.conn.connected:
                        network.conn.join(channel)
                    network.rtc_to_irc(channel, json.dumps({"type": "join", "channel": channel}))
                elif action == "leave":
                    network.rtc_to_irc(channel, json.dumps({"type": "leave", "channel": channel}))
                    if network.conn is not None and network.conn.connected:
                        network.conn.part(channel)
                elif action == "signal":
                    payload = data.get("payload")
                    if isinstance(payload, dict):
                        payload = json.dumps(payload)
                    if isinstance(payload, str):
                        network.rtc_to_irc(channel, payload)
        finally:
            if session in self.rtc_sessions:
                self.rtc_sessions.remove(session)
            for nonce, pending in list(self.rtc_pending.items()):
                if pending is session:
                    del self.rtc_pending[nonce]
            network = session.get("network")
            channel = session.get("channel")
            if network is not None and channel is not None:
                try:
                    network.rtc_to_irc(channel, json.dumps({"type": "leave", "channel": channel}))
                except Exception:
                    pass

        return ws

    async def detect_public_endpoint(self):
"""


def main():
    replace_once(NET, CAPS_OLD, CAPS_NEW, "voice-cap")
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "voice-tagmsg-handler")
    replace_once(NET, JOIN_OLD, JOIN_NEW, "voice-join-skip")
    replace_once(NET, METHODS_OLD, METHODS_NEW, "voice-network-methods")
    replace_once(MAIN, IMPORT_OLD, IMPORT_NEW, "voice-json-import")
    replace_once(MAIN, PATHLIB_OLD, PATHLIB_NEW, "voice-pathlib-import")
    replace_once(MAIN, INIT_OLD, INIT_NEW, "voice-state")
    replace_once(MAIN, ROUTES_OLD, ROUTES_NEW, "voice-routes")
    replace_once(MAIN, EVENT_OLD, EVENT_NEW, "voice-handshake-event")
    replace_once(MAIN, VOICE_OLD, VOICE_NEW, "voice-websocket")


if __name__ == "__main__":
    main()
