# 0015 — take the space icon from the IRCv3 draft/ICON ISUPPORT token
#
# Network icons are advertised by the server as an ISUPPORT token
# ("005 ... draft/ICON=<url>", optionally containing a {size} template), so the
# bridge no longer needs a configured URL: it learns the icon when the network
# connects and applies it to the managed space.
#
# The icon is only uploaded when the space has no avatar yet, so reconnects do
# not re-upload it. SPACEICON stays as an explicit override for networks that do
# not publish the token, and as a way to force a re-apply.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"
SPACE = "heisenbridge/space_room.py"


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


STATE_OLD = """        self.space = None
        self.space_icon = None
"""

STATE_NEW = """        self.space = None
        self.space_icon = None
        # icon advertised by the network via the draft/ICON ISUPPORT token
        self.network_icon = None
"""

REGISTER_OLD = """                self.conn.add_global_handler("note", self.on_standard_reply)
"""

REGISTER_NEW = """                self.conn.add_global_handler("note", self.on_standard_reply)
                self.conn.add_global_handler("featurelist", self.on_featurelist)
"""

HANDLER_OLD = """    def on_standard_reply(self, conn, event) -> None:
"""

HANDLER_NEW = """    def on_featurelist(self, conn, event) -> None:
        # RPL_ISUPPORT: "005 <nick> TOKEN=value ... :are supported by this server"
        for token in event.arguments:
            key, sep, value = token.partition("=")
            if not sep or key.lower() not in ("draft/icon", "icon"):
                continue

            self.network_icon = value.replace("{size}", "512")
            logging.debug(f"Network icon advertised by server: {self.network_icon}")

            if self.space is not None:
                asyncio.ensure_future(self.space.apply_icon())

            return

    def on_standard_reply(self, conn, event) -> None:
"""

CMD_OLD = """    async def cmd_spaceicon(self, args) -> None:
        if args.url is None:
            self.send_notice(f"Space icon: {self.space_icon if self.space_icon else 'not set'}")
            return

        self.space_icon = None if args.url == "-" else args.url
        await self.save()

        if self.space_icon is None:
            self.send_notice("Space icon cleared.")
            return

        self.send_notice(f"Space icon set to {self.space_icon}.")

        if self.space is not None:
            await self.space.apply_icon()
"""

CMD_NEW = """    async def cmd_spaceicon(self, args) -> None:
        if args.url is not None:
            self.space_icon = None if args.url == "-" else args.url
            await self.save()

        icon = self.space_icon or self.network_icon

        if icon is None:
            self.send_notice("No space icon known: the network does not advertise draft/ICON and no URL is set.")
            return

        source = "SPACEICON override" if self.space_icon else "network draft/ICON"
        self.send_notice(f"Space icon: {icon} (from {source}).")

        if self.space is not None:
            await self.space.apply_icon(force=True)
"""

CREATE_OLD = """        if self.network.space_icon:
            await self.apply_icon()
"""

CREATE_NEW = """        if self.network.space_icon or self.network.network_icon:
            await self.apply_icon()
"""

APPLY_OLD = """    async def apply_icon(self) -> None:
        if self.id is None or not self.network.space_icon:
            return

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(self.network.space_icon) as response:
"""

APPLY_NEW = """    async def apply_icon(self, force: bool = False) -> None:
        if self.id is None:
            return

        url = self.network.space_icon or self.network.network_icon
        if not url:
            return

        if not force:
            try:
                current = await self.az.intent.get_state_event(self.id, EventType.ROOM_AVATAR)
                if getattr(current, "url", None):
                    return
            except Exception:
                pass

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
"""


def main():
    replace_once(NET, STATE_OLD, STATE_NEW, "network-icon-state")
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "featurelist-register")
    replace_once(NET, HANDLER_OLD, HANDLER_NEW, "featurelist-handler")
    replace_once(NET, CMD_OLD, CMD_NEW, "spaceicon-override")
    replace_once(SPACE, CREATE_OLD, CREATE_NEW, "icon-on-create")
    replace_once(SPACE, APPLY_OLD, APPLY_NEW, "icon-apply")


if __name__ == "__main__":
    main()
