# 0027 — put the voice widget into every channel room
#
# Adding the widget by hand for every channel is pointless: the bridge created the
# room, it knows the room id and it has the power level to write state there. So
# it registers the widget itself, using the legacy `im.vector.modular.widgets`
# event that clients actually read (Element and Commet/Vommet both use that type,
# not `m.widget`).
#
# The URL carries the room id because clients do not substitute template variables
# in state event widgets. The public base URL comes from `media_url`, which is the
# only place the bridge learns its own public address.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ROOM = "heisenbridge/room.py"
CHANNEL = "heisenbridge/channel_room.py"

WIDGET_TYPE = "im.vector.modular.widgets"
WIDGET_ID = "irc-voice"


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


METHOD_OLD = """    async def set_avatar_from_url(self, url: str) -> None:
"""

METHOD_NEW = """    async def ensure_voice_widget(self) -> None:
        # clients read the legacy Element event type, not m.widget
        if self.id is None:
            return

        base = getattr(self.serv, "media_endpoint", None)
        if not base:
            logging.debug("No public URL configured, skipping the voice widget")
            return

        widget_id = "irc-voice"

        try:
            await self.az.intent.get_state_event(self.id, "im.vector.modular.widgets", widget_id)
            return
        except Exception:
            pass

        url = f"{base.rstrip('/')}/voice/index.html?roomId={self.id}"

        try:
            await self.az.intent.send_state_event(
                self.id,
                "im.vector.modular.widgets",
                {
                    "type": "m.custom",
                    "url": url,
                    "name": "IRC voice",
                    "id": widget_id,
                    "creatorUserId": self.az.bot_mxid,
                    "data": {},
                },
                state_key=widget_id,
            )
            logging.info(f"Added the voice widget to {self.id}")
        except Exception:
            logging.debug(f"Failed to add the voice widget to {self.id}", exc_info=True)

    async def set_avatar_from_url(self, url: str) -> None:
"""

POST_INIT_OLD = """    def cleanup(self) -> None:
        if self.network:
            if self.network.conn and self.network.conn.connected:
                self.network.conn.part(self.name)
"""

POST_INIT_NEW = """    async def post_init(self) -> None:
        await super().post_init()
        await self.ensure_voice_widget()

    def cleanup(self) -> None:
        if self.network:
            if self.network.conn and self.network.conn.connected:
                self.network.conn.part(self.name)
"""


def main():
    replace_once(ROOM, METHOD_OLD, METHOD_NEW, "voice-widget-method")
    replace_once(CHANNEL, POST_INIT_OLD, POST_INIT_NEW, "voice-widget-post-init")


if __name__ == "__main__":
    main()
