# 0010 — away-notify: mirror IRC away state to Matrix presence
#
# The away event type is shared between the WHOIS 301 numeric (two or more
# arguments: nick and message) and the away-notify AWAY command (no arguments,
# the reason sits in the target). Only the latter is a presence update, so the
# handler now branches on the argument count and pushes m.presence for the
# puppet instead of posting a notice into a room.
#
# Presence for appservice users is best effort: servers that refuse it just log
# a debug line.
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


IMPORT_OLD = """from mautrix.util.bridge_state import BridgeStateEvent
"""

IMPORT_NEW = """from mautrix.types import PresenceState
from mautrix.util.bridge_state import BridgeStateEvent
"""

AWAY_OLD = """    def on_away(self, conn, event) -> None:
        if len(event.arguments) < 2:
"""

AWAY_NEW = """    async def _set_presence(self, user_id, status) -> None:
        try:
            await self.az.intent.user(user_id).set_presence(
                PresenceState.UNAVAILABLE if status else PresenceState.ONLINE, status or None
            )
        except Exception:
            logging.debug(f"Failed to set presence for {user_id}", exc_info=True)

    def on_away(self, conn, event) -> None:
        if not event.arguments:
            # away-notify: ":nick!user@host AWAY [:reason]", the reason is the target
            if event.source.nick != conn.real_nickname:
                irc_user_id = self.serv.irc_user_id(self.name, event.source.nick)
                asyncio.ensure_future(self._set_presence(irc_user_id, event.target))
            return

        if len(event.arguments) < 2:
"""

CAPS_OLD = """            "multi-prefix",
            "userhost-in-names",
            "extended-join",
        ]
"""

CAPS_NEW = """            "multi-prefix",
            "userhost-in-names",
            "extended-join",
            "away-notify",
        ]
"""


def main():
    replace_once(NET, IMPORT_OLD, IMPORT_NEW, "import-presence")
    replace_once(NET, AWAY_OLD, AWAY_NEW, "away-presence")
    replace_once(NET, CAPS_OLD, CAPS_NEW, "caps-away")


if __name__ == "__main__":
    main()
