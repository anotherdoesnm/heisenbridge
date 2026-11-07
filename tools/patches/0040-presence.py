# 0040 — actually put the bridge online
#
# The keepalive called set_presence(self.user_id), passing the user id where the
# presence state belongs. ClientAPI.set_presence does presence.value, so a str
# raised AttributeError, which the bare except swallowed once a minute — the
# bridge stayed "offline" in every client while the loop looked healthy.
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


IMPORT_OLD = "from mautrix.types import Membership\n"
IMPORT_NEW = "from mautrix.types import Membership\nfrom mautrix.types import PresenceState\n"

CALL_OLD = """        async def put_presence():
            try:
                await self.az.intent.set_presence(self.user_id)
            except Exception:
                pass
"""

CALL_NEW = """        async def put_presence():
            try:
                await self.az.intent.set_presence(PresenceState.ONLINE, ignore_cache=True)
            except Exception:
                logging.exception("Setting presence failed")
"""


def main():
    replace_once(MAIN, IMPORT_OLD, IMPORT_NEW, "presence-import")
    replace_once(MAIN, CALL_OLD, CALL_NEW, "presence-call")


if __name__ == "__main__":
    main()
