# 0018 — accept a DM invite that is not marked as direct
#
# Clients only put is_direct on the invite that creates a direct room, so an
# invite into a room that already exists (a DM the user made earlier, a typo they
# corrected) arrives without the flag and the bridge silently drops it:
#
#   if not event.content.is_direct: return
#
# and the invite just hangs there with nothing but a debug line in the log. Join
# the room, look at it, and keep it only when it really is a 1:1 conversation with
# the inviter; anything else is left again immediately.
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


CHECK_OLD = """            if not event.content.is_direct:
                logging.debug("Got an invite to non-direct room, ignoring")
                return
"""

CHECK_NEW = """            if not event.content.is_direct and not await self._invite_is_direct(event.room_id, event.sender):
                logging.info(f"Got an invite to non-direct room {event.room_id}, ignoring")
                return
"""

METHOD_OLD = """    async def detect_public_endpoint(self):
"""

METHOD_NEW = """    async def _invite_is_direct(self, room_id: str, inviter: str) -> bool:
        # is_direct is only set on the invite that creates a DM, so an invite into
        # an existing direct room has no flag. Join briefly and keep the room only
        # when it turns out to be a 1:1 conversation with the inviter.
        try:
            await self.az.intent.join_room(room_id)
            members = await self.az.intent.get_room_members(room_id)
        except Exception:
            logging.exception(f"Failed to inspect the invite to {room_id}")
            return False

        if len(members) == 2 and inviter in members:
            logging.info(f"Room {room_id} is 1:1, treating the invite as direct")
            return True

        logging.info(f"Room {room_id} has {len(members)} members, leaving again")
        try:
            await self.az.intent.leave_room(room_id)
        except Exception:
            logging.exception(f"Failed to leave {room_id}")
        return False

    async def detect_public_endpoint(self):
"""


def main():
    replace_once(MAIN, CHECK_OLD, CHECK_NEW, "invite-is-direct")
    replace_once(MAIN, METHOD_OLD, METHOD_NEW, "invite-check-method")


if __name__ == "__main__":
    main()
