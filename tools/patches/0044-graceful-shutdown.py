# 0044 — quit IRC cleanly on SIGTERM
#
# docker compose sends SIGTERM when a container is recreated, and the bridge had
# no handler, so the process died with the TCP connection open. The server kept
# the old session around and the fresh container could find its nick taken,
# ending up as doesnm_ for a while.
#
# Send QUIT to every connected network and give the write a moment to flush.
#
# This does not make a redeploy lossless — the IRC connection still drops, and
# messages sent during the gap are lost. True continuity needs a bouncer between
# the bridge and the network.
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


IMPORT_OLD = "import random\nimport re\n"
IMPORT_NEW = "import random\nimport re\nimport signal\n"

SHUTDOWN_OLD = "    async def run(self, listen_address, listen_port, homeserver_url, owner, safe_mode, media_proxy):\n"

SHUTDOWN_NEW = """    async def _graceful_shutdown(self) -> None:
        # docker sends SIGTERM on redeploy, quit cleanly so the server drops the
        # session at once and the nick is free when the new container connects
        logging.info("Shutting down, sending QUIT to IRC networks")

        for room in list(self._rooms.values()):
            if type(room) != NetworkRoom or room.conn is None or not room.conn.connected:
                continue

            try:
                room.conn.quit("bridge restarting")
            except Exception:
                logging.exception(f"Sending QUIT to {room.name} failed")

        await asyncio.sleep(1)
        os._exit(0)

    async def run(self, listen_address, listen_port, homeserver_url, owner, safe_mode, media_proxy):
"""

WAIT_OLD = """        await asyncio.Event().wait()


async def async_main():
"""

WAIT_NEW = """        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(self._graceful_shutdown()))

        await asyncio.Event().wait()


async def async_main():
"""


def main():
    replace_once(MAIN, IMPORT_OLD, IMPORT_NEW, "shutdown-import")
    replace_once(MAIN, SHUTDOWN_OLD, SHUTDOWN_NEW, "shutdown-method")
    replace_once(MAIN, WAIT_OLD, WAIT_NEW, "shutdown-signal")


if __name__ == "__main__":
    main()
