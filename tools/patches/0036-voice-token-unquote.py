# 0036 — accept a voice token for a percent-encoded room id
#
# Clients rewrite widget URLs, and a room id that arrived percent-encoded
# (`%21room%3Aserver`) is not always decoded before it reaches the widget, so the
# HMAC was computed over the wrong string and the bridge answered "bad voice
# token" even though the token was right for the real room id.
#
# Compare against the decoded form as well.
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


CHECK_OLD = """                    if room_id and token and self.rtc_token(room_id) == token:
                        self.rtc_bind_room(session, room_id)
"""

CHECK_NEW = """                    decoded = urllib.parse.unquote(room_id) if room_id else ""

                    if room_id and token and token in (self.rtc_token(room_id), self.rtc_token(decoded)):
                        self.rtc_bind_room(session, decoded or room_id)
"""


def main():
    replace_once(MAIN, CHECK_OLD, CHECK_NEW, "voice-token-unquote")


if __name__ == "__main__":
    main()
