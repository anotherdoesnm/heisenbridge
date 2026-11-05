# 0017 — let the server judge power levels instead of mautrix
#
# mautrix refuses to send a state event when its own bookkeeping says the bridge
# has too little power:
#
#   IntentError: Power level of @heisenbridge:... is not enough for m.room.topic
#
# Room version 12 (MSC4289) stopped writing the creator into
# m.room.power_levels.users, so a room the bridge itself created looks like a
# plain power level 0 room to that check, and topic/name/avatar sync is dropped
# locally while the homeserver would have accepted it.
#
# The homeserver is the authority on power levels, so the pre-check is replaced
# with a no-op and a real M_FORBIDDEN is allowed to come back instead.
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


IMPORT_OLD = """from mautrix.appservice import AppService as MauService
"""

IMPORT_NEW = """from mautrix.appservice import AppService as MauService
from mautrix.appservice.api.intent import IntentAPI
"""

HOOK_OLD = """from heisenbridge.websocket import AppserviceWebsocket
"""

HOOK_NEW = """from heisenbridge.websocket import AppserviceWebsocket


# Room version 12 (MSC4289) does not list the creator in m.room.power_levels, so
# mautrix's local power level check sees the bridge as a plain user and refuses
# state events in rooms the bridge created itself. Let the server decide.
async def _ensure_has_power_level_for(self, room_id, event_type, state_key="") -> None:
    return


IntentAPI._ensure_has_power_level_for = _ensure_has_power_level_for
"""


def main():
    replace_once(MAIN, IMPORT_OLD, IMPORT_NEW, "intent-import")
    replace_once(MAIN, HOOK_OLD, HOOK_NEW, "power-level-hook")


if __name__ == "__main__":
    main()
