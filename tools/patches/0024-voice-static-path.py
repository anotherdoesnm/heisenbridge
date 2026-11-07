# 0024 — serve the voice widget from inside the package
#
# 0023 pointed the static route at the repository root, but .dockerignore only
# whitelists heisenbridge/, tools/ and a few files, so the widget never made it
# into the image and add_static() raised ValueError on startup — which crash
# looped the bridge.
#
# Ship the widget as package data instead and never let a missing directory take
# the whole bridge down.
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


ROUTES_OLD = """        self.az.app.router.add_static("/voice", pathlib.Path(__file__).resolve().parent.parent / "voice")
"""

ROUTES_NEW = """        try:
            self.az.app.router.add_static("/voice", pathlib.Path(__file__).resolve().parent / "voice")
        except ValueError:
            logging.warning("Voice widget files are missing, /voice/ is unavailable")
"""


def main():
    replace_once(MAIN, ROUTES_OLD, ROUTES_NEW, "voice-static-path")


if __name__ == "__main__":
    main()
