#!/usr/bin/env python3
"""Apply this fork's patches to the pristine upstream sources.

Every patch is a standalone file in tools/patches, applied in name order. The
fork keeps the upstream tree untouched so the delta stays reviewable and a
rebase cannot silently ship an unpatched image: each patch asserts that its
anchors are still present and exits non-zero otherwise.

Run from the repository root (the Dockerfile does this at build time):

    python3 tools/apply_patches.py

Patches are idempotent: applying them twice is a no-op.
"""
import pathlib
import runpy
import sys

PATCHES = pathlib.Path(__file__).resolve().parent / "patches"


def main():
    for path in sorted(PATCHES.glob("[0-9]*.py")):
        print(f"--- {path.name}")
        sys.argv = [str(path)]
        runpy.run_path(str(path), run_name="__main__")

    print("all patches applied")


if __name__ == "__main__":
    main()
