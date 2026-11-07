# 0049 — keep the IRC session alive across a redeploy
#
# ObbyIRCd implements IRCv3 draft/persistence: an authenticated client with
# persistence on leaves a ghost behind when it disconnects, and the next
# connection with the same account takes its channels back. The bridge did not
# ask for it, so every restart dropped the session, the nick could be taken and
# all channels had to be joined again from scratch.
#
# Negotiate draft/persistence and switch it on after registration. The ghost
# keeps the nick and the channel memberships; on reconnect the server sends the
# JOINs itself.
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


CAPS_OLD = """            "obsidianirc/voice",
            "draft/chathistory",
        ]
"""

CAPS_NEW = """            "obsidianirc/voice",
            "draft/chathistory",
            "draft/persistence",
        ]
"""

WELCOME_OLD = """        if "draft/metadata-2" in self.caps_enabled:
            # subscribe once per connection, the server then pushes the avatar of
            # every channel we join and of every user in it
            self.conn.send_raw("METADATA * SUB avatar")
"""

WELCOME_NEW = """        if "draft/metadata-2" in self.caps_enabled:
            # subscribe once per connection, the server then pushes the avatar of
            # every channel we join and of every user in it
            self.conn.send_raw("METADATA * SUB avatar")

        if "draft/persistence" in self.caps_enabled:
            # leave a ghost behind on disconnect and take its channels back on
            # reconnect, so a bridge restart does not drop the IRC session
            self.conn.send_raw("PERSISTENCE SET ON")
"""


def main():
    replace_once(NET, CAPS_OLD, CAPS_NEW, "persistence-cap")
    replace_once(NET, WELCOME_OLD, WELCOME_NEW, "persistence-command")


if __name__ == "__main__":
    main()
