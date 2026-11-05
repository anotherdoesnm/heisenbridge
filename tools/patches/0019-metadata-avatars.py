# 0019 — IRCv3 metadata: avatars for channels and users
#
# Servers that implement draft/metadata-2 publish key/value metadata per target.
# The interesting key for a bridge is "avatar": the channel's icon and the icon of
# every user. Subscribe to it once per connection and the server pushes the
# current values on join (and updates as they change), so nothing has to be
# polled.
#
# Channel avatars become the Matrix room avatar, user avatars become the puppet's
# profile avatar. Images are downloaded and re-uploaded to the homeserver because
# Matrix wants an mxc URI, and the result is cached per URL so a busy channel does
# not upload the same icon over and over.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"
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


CAPS_OLD = """            "draft/read-marker",
        ]
"""

CAPS_NEW = """            "draft/read-marker",
            "batch",
            "draft/metadata-2",
        ]
"""

REGISTER_OLD = """                self.conn.add_global_handler("welcome", self.on_welcome)
"""

REGISTER_NEW = """                self.conn.add_global_handler("welcome", self.on_welcome)
                self.conn.add_global_handler("metadata", self.on_metadata)
                self.conn.add_global_handler("761", self.on_keyvalue)  # RPL_KEYVALUE
"""

METHODS_OLD = """    def on_welcome(self, conn, event) -> None:
        self.on_server_message(conn, event)
"""

METHODS_NEW = """    def on_metadata(self, conn, event) -> None:
        # METADATA <Target> <Key> <Visibility> <Value>
        if len(event.arguments) < 3:
            return

        target = event.arguments[0]
        key = event.arguments[1].lower()
        value = event.arguments[-1]

        if key != "avatar":
            return

        logging.debug(f"Avatar metadata for {target}: {value}")
        asyncio.ensure_future(self.apply_avatar(target, value))

    def on_keyvalue(self, conn, event) -> None:
        # RPL_KEYVALUE (761): "<client> <Target> <Key> <Visibility> :<Value>"
        arguments = event.arguments[1:]
        if len(arguments) < 3:
            return

        target = arguments[0]
        key = arguments[1].lower()
        value = arguments[-1]

        if key != "avatar":
            return

        asyncio.ensure_future(self.apply_avatar(target, value))

    async def apply_avatar(self, target: str, url: str) -> None:
        if not url or url in ("*", "-") or not url.startswith(("http://", "https://")):
            return

        # a channel we are in: the avatar belongs to the Matrix room
        if target.startswith(("#", "&", "+", "!")):
            room = self.rooms.get(target.lower())
            if room is not None:
                await room.set_avatar_from_url(url)
            return

        if self.conn is None or target == self.conn.real_nickname:
            return

        # anything else is a nick: the avatar belongs to the puppet
        try:
            user_id = await self.serv.ensure_irc_user_id(self.name, target)
        except Exception:
            logging.debug(f"Failed to register a puppet for {target}", exc_info=True)
            return

        mxc = await self.serv.fetch_mxc(url)
        if mxc is None:
            return

        try:
            await self.az.intent.user(user_id).set_avatar_url(mxc)
        except Exception:
            logging.debug(f"Failed to set the avatar of {user_id}", exc_info=True)

    def on_welcome(self, conn, event) -> None:
        self.on_server_message(conn, event)

        if "draft/metadata-2" in self.caps_enabled:
            # subscribe once per connection, the server then pushes the avatar of
            # every channel we join and of every user in it
            self.conn.send_raw("METADATA * SUB avatar")
"""

IMPORTS_OLD = """import logging
import re
"""

IMPORTS_NEW = """import asyncio
import logging
import re
"""

ROOM_METHOD_OLD = """    async def save(self) -> None:
        config = self.to_config()
        config["type"] = type(self).__name__
        config["user_id"] = self.user_id
        await self.az.intent.set_account_data("irc", config, self.id)
"""

ROOM_METHOD_NEW = """    async def save(self) -> None:
        config = self.to_config()
        config["type"] = type(self).__name__
        config["user_id"] = self.user_id
        await self.az.intent.set_account_data("irc", config, self.id)

    async def set_avatar_from_url(self, url: str) -> None:
        # metadata for a channel can arrive while the room is still being created
        for _ in range(15):
            if self.id is not None:
                break
            await asyncio.sleep(1)

        if self.id is None:
            return

        mxc = await self.serv.fetch_mxc(url)
        if mxc is None:
            return

        try:
            current = await self.az.intent.get_state_event(self.id, EventType.ROOM_AVATAR)
            if getattr(current, "url", None) == mxc:
                return
        except Exception:
            pass

        try:
            await self.az.intent.set_room_avatar(self.id, mxc)
            logging.debug(f"Set the avatar of {self.id} to {mxc}")
        except Exception:
            logging.debug(f"Failed to set the avatar of {self.id}", exc_info=True)
"""

FETCH_OLD = """    def mxc_to_url(self, mxc: str, filename=None):
"""

FETCH_NEW = """    async def fetch_mxc(self, url: str) -> str | None:
        # download an image and upload it to the homeserver, cached per URL so the
        # same avatar is not uploaded twice
        if url in self.avatar_cache:
            return self.avatar_cache[url]

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status != 200:
                        logging.debug(f"Avatar fetch for {url} returned {response.status}")
                        return None

                    data = await response.read()
                    mime_type = response.headers.get("Content-Type", "image/png")
        except Exception:
            logging.debug(f"Failed to fetch {url}", exc_info=True)
            return None

        if len(data) > self.MAX_AVATAR_BYTES:
            logging.debug(f"Refusing {url}: {len(data)} bytes is too large")
            return None

        try:
            mxc = await self.az.intent.upload_media(data, mime_type=mime_type)
        except Exception:
            logging.debug(f"Failed to upload {url}", exc_info=True)
            return None

        self.avatar_cache[url] = mxc
        return mxc

    def mxc_to_url(self, mxc: str, filename=None):
"""

CACHE_OLD = """        self._rooms = {}
        self._users = {}
"""

CACHE_NEW = """        self._rooms = {}
        self._users = {}
        self.avatar_cache = {}
"""

MAX_OLD = """    DEFAULT_MEDIA_PATH = "/_heisenbridge/media/{server}/{media_id}/{checksum}{filename}"
"""

MAX_NEW = """    DEFAULT_MEDIA_PATH = "/_heisenbridge/media/{server}/{media_id}/{checksum}{filename}"
    MAX_AVATAR_BYTES = 4 * 1024 * 1024
"""


def main():
    replace_once(NET, CAPS_OLD, CAPS_NEW, "metadata-caps")
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "metadata-handlers")
    replace_once(NET, METHODS_OLD, METHODS_NEW, "metadata-methods")
    replace_once(ROOM, IMPORTS_OLD, IMPORTS_NEW, "room-asyncio-import")
    replace_once(ROOM, ROOM_METHOD_OLD, ROOM_METHOD_NEW, "room-avatar-from-url")
    replace_once(MAIN, FETCH_OLD, FETCH_NEW, "fetch-mxc")
    replace_once(MAIN, CACHE_OLD, CACHE_NEW, "avatar-cache")
    replace_once(MAIN, MAX_OLD, MAX_NEW, "max-avatar-bytes")


if __name__ == "__main__":
    main()
