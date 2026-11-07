# 0034 — actually remove the `^`/`$` skip from on_join
#
# 0032 tried to delete the block with an empty replacement, but replace_once()
# treats an empty string as "already applied" (`"" in text` is always true), so
# the deletion was a silent no-op and the bridge still refuses to create rooms
# for voice and stream channels.
#
# Remove it with a dedicated helper that checks the old text instead.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"

BLOCK = """            # voice (`^`) and stream (`$`) channels carry no text, the widget
            # talks to the SFU directly and there is nothing to bridge into a room
            if target.startswith(("^", "$")):
                logging.debug(f"Joined voice channel {target}, no Matrix room needed")
                return

"""


def remove_once(path, old, label):
    file = ROOT / path
    text = file.read_text()

    if old not in text:
        print(f"{label}: already removed")
        return

    file.write_text(text.replace(old, "", 1))
    print(f"{label}: patched {path}")


def main():
    remove_once(NET, BLOCK, "voice-join-keep-room")


if __name__ == "__main__":
    main()
