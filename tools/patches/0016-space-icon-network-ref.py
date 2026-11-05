# 0016 — keep the network reference on loaded spaces
#
# A SpaceRoom only ever learned its network in SpaceRoom.create(), where the
# attribute was described as "only used in create_finalize". Spaces restored from
# account data therefore have no network attribute, and the draft/ICON handler
# blew up with:
#
#   AttributeError: 'SpaceRoom' object has no attribute 'network'
#
# which is exactly the path that runs after a bridge restart. Set the back
# reference in post_init() (where the space is linked to its network anyway) and
# make apply_icon() resolve the network defensively so a dangling space can never
# raise from a background task.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SPACE = "heisenbridge/space_room.py"


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


POST_INIT_OLD = """            network.space = self
            logging.debug(f"Space {self.id} attached to network {network.id}")
"""

POST_INIT_NEW = """            network.space = self
            # keep the back reference: apply_icon() reads the icon from the network
            self.network = network
            logging.debug(f"Space {self.id} attached to network {network.id}")
"""

APPLY_OLD = """        url = self.network.space_icon or self.network.network_icon
        if not url:
            return
"""

APPLY_NEW = """        network = getattr(self, "network", None)
        if network is None:
            network = self.serv._rooms.get(self.network_id)

        if network is None:
            return

        url = network.space_icon or network.network_icon
        if not url:
            return
"""


def main():
    replace_once(SPACE, POST_INIT_OLD, POST_INIT_NEW, "space-network-ref")
    replace_once(SPACE, APPLY_OLD, APPLY_NEW, "icon-network-lookup")


if __name__ == "__main__":
    main()
