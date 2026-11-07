# 0045 — kick puppets as the bridge, not as themselves
#
# When an IRC user leaves a channel with a reason, the room queue tries to show
# it as a kick, but it used the intent of the user being kicked:
#
#   await self.az.intent.user(event["user_id"]).kick_user(self.id, event["user_id"], ...)
#
# which is the same user id on both sides, so the homeserver answered
# "M_FORBIDDEN: You cannot kick yourself" and the event was lost with a
# traceback in the log. The appservice intent can kick its own puppets.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ROOM = "heisenbridge/room.py"


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


KICK_OLD = """                    if event["user_id"] in self.members:
                        if event["reason"] is not None:
                            await self.az.intent.user(event["user_id"]).kick_user(
                                self.id, event["user_id"], event["reason"]
                            )
                        else:
                            await self.az.intent.user(event["user_id"]).leave_room(self.id)
"""

KICK_NEW = """                    if event["user_id"] in self.members:
                        if event["user_id"] in (self.serv.user_id, self.user_id):
                            # never kick ourselves, just drop the membership
                            pass
                        elif event["reason"] is not None:
                            await self.az.intent.kick_user(self.id, event["user_id"], event["reason"])
                        else:
                            await self.az.intent.user(event["user_id"]).leave_room(self.id)
"""


def main():
    replace_once(ROOM, KICK_OLD, KICK_NEW, "kick-puppet")


if __name__ == "__main__":
    main()
