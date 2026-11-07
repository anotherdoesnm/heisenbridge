# 0046 — the rest of the NAMES dump on reconnect
#
# 0042 only silenced the "Synchronizing members: ..." summary. on_endofnames
# also prints the mode breakdown ("Users with owner (~): mattf") and the
# "Member sync is set to ..., skipping invites." line, so a reconnect still
# posted three messages per channel. Wrap the whole report in the same quiet
# check; the member sync itself still runs.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHAN = "heisenbridge/channel_room.py"


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


OLD = """        # show modes from top to bottom
        for mode, name in modenames.items():
            if mode in modes:
                nicks = sorted(modes[mode], key=str.casefold)
                self.send_notice(f"Users with {name} ({mode}): {', '.join(nicks)}")
                del modes[mode]

        # show unknown modes
        for mode, nicks in modes.items():
            nicks = sorted(nicks, key=str.casefold)
            self.send_notice(f"Users with '{mode}': {', '.join(nicks)}")

        # show everyone else
        if len(others) > 0:
            others = sorted(others, key=str.casefold)
            self.send_notice(f"Users: {', '.join(others)}")

        if self.member_sync == "full":
            for irc_user_id, nick in to_add:
                self._add_puppet(nick)
        else:
            self.send_notice(f"Member sync is set to {self.member_sync}, skipping invites.")
"""

NEW = """        # show modes from top to bottom
        for mode, name in modenames.items():
            if mode in modes:
                nicks = sorted(modes[mode], key=str.casefold)

                if not self._quiet():
                    self.send_notice(f"Users with {name} ({mode}): {', '.join(nicks)}")

                del modes[mode]

        # show unknown modes
        for mode, nicks in modes.items():
            nicks = sorted(nicks, key=str.casefold)

            if not self._quiet():
                self.send_notice(f"Users with '{mode}': {', '.join(nicks)}")

        # show everyone else
        if len(others) > 0:
            others = sorted(others, key=str.casefold)

            if not self._quiet():
                self.send_notice(f"Users: {', '.join(others)}")

        if self.member_sync == "full":
            for irc_user_id, nick in to_add:
                self._add_puppet(nick)
        elif not self._quiet():
            self.send_notice(f"Member sync is set to {self.member_sync}, skipping invites.")
"""


def main():
    replace_once(CHAN, OLD, NEW, "quiet-names")


if __name__ == "__main__":
    main()
