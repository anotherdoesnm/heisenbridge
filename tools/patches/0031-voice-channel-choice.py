# 0031 — let the widget pick `^voice` or `$stream`
#
# The channel is derived from the room name, which is fine for voice (`#bots` ->
# `^bots`) but not for stream channels, where obby uses `$`. Let the widget ask
# for a specific channel and remember it for the rest of the session.
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


JOIN_OLD = """                if action == "join":
                    if network.conn is not None and network.conn.connected:
                        network.conn.join(channel)
                    network.rtc_to_irc(channel, json.dumps({"type": "join", "channel": channel}))
"""

JOIN_NEW = """                if action == "join":
                    requested = (data.get("channel") or channel).lower()

                    if requested.startswith(("^", "$")):
                        channel = requested
                        session["channel"] = requested

                    if network.conn is not None and network.conn.connected:
                        network.conn.join(channel)
                    network.rtc_to_irc(channel, json.dumps({"type": "join", "channel": channel}))
"""


def main():
    replace_once(MAIN, JOIN_OLD, JOIN_NEW, "voice-channel-choice")


if __name__ == "__main__":
    main()
