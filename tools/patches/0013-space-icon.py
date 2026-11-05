# 0013 — give the managed space a network icon
#
# The bridge creates the space, so it is the only member with power to set its
# avatar; the invited user has power level 0 there. SPACEICON stores an image URL
# on the network room and the space fetches, uploads and applies it, both when
# the space is created and immediately when the command is run on an existing
# space.
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
"""

STATE_NEW = """        self.space = None
        self.space_icon = None
"""

LOAD_OLD = """        if "caps" in config:
            # union with the defaults so capabilities added by a new bridge version
            # reach networks that already have their list stored in account data
            self.caps = sorted(set(config["caps"]) | set(self.caps))
"""

LOAD_NEW = """        if "caps" in config:
            # union with the defaults so capabilities added by a new bridge version
            # reach networks that already have their list stored in account data
            self.caps = sorted(set(config["caps"]) | set(self.caps))

        if "space_icon" in config:
            self.space_icon = config["space_icon"]
"""

SAVE_OLD = """            "caps": self.caps,
            "forward": self.forward,
        }
"""

SAVE_NEW = """            "caps": self.caps,
            "forward": self.forward,
            "space_icon": self.space_icon,
        }
"""

CMD_OLD = """        cmd = CommandParser(prog="SPACE", description="create a managed Matrix space for this network")
        self.commands.register(cmd, self.cmd_space)
"""

CMD_NEW = """        cmd = CommandParser(prog="SPACE", description="create a managed Matrix space for this network")
        self.commands.register(cmd, self.cmd_space)

        cmd = CommandParser(
            prog="SPACEICON", description="set the icon of the managed space from an image URL"
        )
        cmd.add_argument("url", nargs="?", help="image URL, or '-' to clear it")
        self.commands.register(cmd, self.cmd_spaceicon)
"""

METHOD_OLD = """    async def cmd_space(self, args) -> None:
"""

METHOD_NEW = """    async def cmd_spaceicon(self, args) -> None:
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

    async def cmd_space(self, args) -> None:
"""

ICON_CALL_OLD = """        self.id = resp["room_id"]
        self.serv.register_room(self)
        await self.save()
"""

ICON_CALL_NEW = """        self.id = resp["room_id"]
        self.serv.register_room(self)
        await self.save()

        if self.network.space_icon:
            await self.apply_icon()
"""

ICON_METHOD_OLD = """    async def attach(self, room_id) -> None:
"""

ICON_METHOD_NEW = """    async def apply_icon(self) -> None:
        if self.id is None or not self.network.space_icon:
            return

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(self.network.space_icon) as response:
                    if response.status != 200:
                        logging.debug(f"Space icon fetch returned {response.status}")
                        return

                    data = await response.read()
                    mime_type = response.headers.get("Content-Type", "image/png")

            mxc = await self.az.intent.upload_media(data, mime_type=mime_type)
            await self.az.intent.send_state_event(self.id, EventType.ROOM_AVATAR, content={"url": mxc})
        except Exception:
            logging.debug("Failed to set the space icon", exc_info=True)

    async def attach(self, room_id) -> None:
"""


def main():
    replace_once(NET, STATE_OLD, STATE_NEW, "space-icon-state")
    replace_once(NET, LOAD_OLD, LOAD_NEW, "space-icon-load")
    replace_once(NET, SAVE_OLD, SAVE_NEW, "space-icon-save")
    replace_once(NET, CMD_OLD, CMD_NEW, "space-icon-command")
    replace_once(NET, METHOD_OLD, METHOD_NEW, "space-icon-cmd-method")
    replace_once(SPACE, ICON_CALL_OLD, ICON_CALL_NEW, "space-icon-on-create")
    replace_once(SPACE, ICON_METHOD_OLD, ICON_METHOD_NEW, "space-icon-method")


if __name__ == "__main__":
    main()
