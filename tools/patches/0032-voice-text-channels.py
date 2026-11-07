# 0032 — `^`/`$` channels are text channels too
#
# 0023 stopped the bridge from creating Matrix rooms for voice and stream
# channels, which quietly removed their text side: upstream heisenbridge joined
# them like any other channel, just without voice.
#
# Create the room again and derive the widget's channel from the room name while
# keeping its prefix, so `^tv` stays `^tv` and `$tv` stays `$tv`.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NET = "heisenbridge/network_room.py"
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


JOIN_OLD = """            # voice (`^`) and stream (`$`) channels carry no text, the widget
            # talks to the SFU directly and there is nothing to bridge into a room
            if target.startswith(("^", "$")):
                logging.debug(f"Joined voice channel {target}, no Matrix room needed")
                return

"""

JOIN_NEW = ""

CHANNEL_OLD = """        channel = "^" + room.name.lstrip("#!+").lower()
"""

CHANNEL_NEW = """        name = room.name or ""
        prefix = name[:1] if name[:1] in ("^", "$") else "^"
        channel = prefix + name.lstrip("^$#!+").lower()
"""


def main():
    replace_once(NET, JOIN_OLD, JOIN_NEW, "voice-join-keep-room")
    replace_once(MAIN, CHANNEL_OLD, CHANNEL_NEW, "voice-channel-prefix")


if __name__ == "__main__":
    main()
