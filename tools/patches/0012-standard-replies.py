# 0012 — standard-replies: show FAIL/WARN/NOTE as readable notices
#
# With standard-replies the server reports problems as FAIL/WARN/NOTE with a
# command, a code and a description instead of bare numerics. The generic
# unhandled-events handler dumps the raw arguments, which loses the distinction;
# this formats them as "<LEVEL>: <description> (<command> <code>)".
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


REGISTER_OLD = """                self.conn.add_global_handler("batch", self.on_batch)
"""

REGISTER_NEW = """                self.conn.add_global_handler("batch", self.on_batch)
                self.conn.add_global_handler("fail", self.on_standard_reply)
                self.conn.add_global_handler("warn", self.on_standard_reply)
                self.conn.add_global_handler("note", self.on_standard_reply)
"""

HANDLER_OLD = """    def on_batch(self, conn, event) -> None:
"""

HANDLER_NEW = """    def on_standard_reply(self, conn, event) -> None:
        # FAIL/WARN/NOTE <command> <code> :description
        parts = event.arguments
        command = parts[0] if len(parts) > 0 else ""
        code = parts[1] if len(parts) > 1 else ""
        description = parts[2] if len(parts) > 2 else ""

        detail = " ".join(part for part in (command, code) if part)
        level = event.type.upper()

        if detail:
            self.send_notice(f"{level}: {description} ({detail})")
        else:
            self.send_notice(f"{level}: {description}")

    def on_batch(self, conn, event) -> None:
"""

CAPS_OLD = """            "away-notify",
            "draft/multiline",
        ]
"""

CAPS_NEW = """            "away-notify",
            "draft/multiline",
            "standard-replies",
        ]
"""


def main():
    replace_once(NET, REGISTER_OLD, REGISTER_NEW, "standard-reply-register")
    replace_once(NET, HANDLER_OLD, HANDLER_NEW, "standard-reply-handler")
    replace_once(NET, CAPS_OLD, CAPS_NEW, "caps-standard-replies")


if __name__ == "__main__":
    main()
