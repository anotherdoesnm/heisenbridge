# 0020 — keep the avatar URL cache in the bridge config
#
# 0019 caches downloaded avatars in memory only, so every restart uploads all of
# them again: the mxc URI is new, the room avatar looks different and the puppet
# profile is rewritten. Store the URL to mxc mapping in the bridge config instead
# (it is account data on the bridge user, so it survives restarts) and keep it
# bounded.
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


def remove_once(path, old, label):
    file = ROOT / path
    text = file.read_text()

    if old not in text:
        print(f"{label}: already removed")
        return

    file.write_text(text.replace(old, "", 1))
    print(f"{label}: patched {path}")


LOOKUP_OLD = """        # download an image and upload it to the homeserver, cached per URL so the
        # same avatar is not uploaded twice
        if url in self.avatar_cache:
            return self.avatar_cache[url]
"""

LOOKUP_NEW = """        # download an image and upload it to the homeserver, cached per URL so the
        # same avatar is not uploaded twice and a restart does not re-upload them
        cache = self.config.setdefault("avatar_cache", {})

        if url in cache:
            return cache[url]
"""

STORE_OLD = """        self.avatar_cache[url] = mxc
        return mxc
"""

STORE_NEW = """        cache[url] = mxc

        # avatar URLs carry a cache buster, so old entries never come back
        while len(cache) > self.MAX_AVATAR_CACHE:
            del cache[next(iter(cache))]

        await self.save()
        return mxc
"""

INIT_OLD = """        self._users = {}
        self.avatar_cache = {}
"""

MAX_OLD = """    MAX_AVATAR_BYTES = 4 * 1024 * 1024
"""

MAX_NEW = """    MAX_AVATAR_BYTES = 4 * 1024 * 1024
    MAX_AVATAR_CACHE = 512
"""


def main():
    replace_once(MAIN, LOOKUP_OLD, LOOKUP_NEW, "avatar-cache-lookup")
    replace_once(MAIN, STORE_OLD, STORE_NEW, "avatar-cache-store")
    remove_once(MAIN, INIT_OLD, "avatar-cache-init")
    replace_once(MAIN, MAX_OLD, MAX_NEW, "avatar-cache-limit")


if __name__ == "__main__":
    main()
