#!/usr/bin/env python3
"""Apply this fork's changes to the pristine upstream sources.

The fork deliberately keeps the upstream tree untouched and carries its delta
as small, anchored rewrites in this file.  That makes the delta easy to review
and easy to rebase (or to submit upstream as a PR), and it means an upstream
change can never silently ship an unpatched image: every patch asserts that its
anchor is still present and exits non-zero otherwise.

Run from the repository root (the Dockerfile does this at build time):

    python3 tools/apply_patches.py

Patches are idempotent: applying them twice is a no-op.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def replace_once(path, old, new, label):
    file = ROOT / path
    text = file.read_text()

    if new in text:
        print(f"{label}: already applied")
        return

    if old not in text:
        sys.exit(f"{label}: anchor not found in {path} — upstream changed, update this patch")

    file.write_text(text.replace(old, new, 1))
    print(f"{label}: patched {path}")


# ---------------------------------------------------------------------------
# 0001 — CAP negotiation: multi-line replies and capabilities carrying a value
#
# `CAP LS`/`CAP ACK` may be split over several lines, where every continuation
# line has a "*" between the subcommand and the capability list, e.g.
#
#     :irc.example.com CAP * LS * :sasl=PLAIN,TOTP away-notify
#     :irc.example.com CAP * LS :draft/chathistory
#
# The upstream code reads a single reply and takes arguments[1] as the list, so
# on such servers it ends up with ["*"] as the supported set, drops every
# requested capability and then fails SASL with "server does not support it".
#
# Capabilities may also carry a value (sasl=PLAIN,EXTERNAL), while the filter
# compares full strings, so `sasl` never matches even on single-line replies.
# ---------------------------------------------------------------------------

CAP_OLD = """                    try:
                        self.conn.cap("LS")
                        self.caps_task = asyncio.ensure_future(self.conn.expect("cap", 10))
                        (connection, event) = await self.caps_task
                        self.caps_task = None

                        if self.conn is None:
                            return

                        if len(event.arguments) > 1 and event.arguments[0] == "LS":
                            self.caps_supported = event.arguments[1].split()
                            self.send_notice(f"Capabilities supported by server: {', '.join(self.caps_supported)}")

                            # filter all unsupported caps away
                            caps_req = [cap for cap in caps_req if cap in self.caps_supported]

                        if caps_req:
                            self.send_notice(f"Capabilities requested: {', '.join(caps_req)}")
                            self.conn.cap("REQ", *caps_req)

                            self.caps_task = asyncio.ensure_future(self.conn.expect("cap", 10))
                            (connection, event) = await self.caps_task
                            self.caps_task = None

                            if self.conn is None:
                                return

                            if len(event.arguments) > 1:
                                if event.arguments[0] == "ACK":
                                    self.caps_enabled = event.arguments[1].split()
                                    self.send_notice(
                                        f"Capabilities negotiated with server: {', '.join(self.caps_enabled)}"
                                    )
                                elif event.arguments[0] == "NAK":
                                    self.send_notice("Capabilities request was rejected.")
                        else:
                            self.send_notice("No capabilities requested.")
"""

CAP_NEW = """                    try:
                        (_, self.caps_supported) = await self._cap_exchange("LS")
                        self.send_notice(f"Capabilities supported by server: {', '.join(self.caps_supported)}")

                        if self.conn is None:
                            return

                        # filter all unsupported caps away, comparing names only (CAP LS may carry a value)
                        supported = {cap.split("=", 1)[0] for cap in self.caps_supported}
                        caps_req = [cap for cap in caps_req if cap.split("=", 1)[0] in supported]

                        if caps_req:
                            self.send_notice(f"Capabilities requested: {', '.join(caps_req)}")

                            (subcommand, self.caps_enabled) = await self._cap_exchange("REQ", *caps_req)

                            if subcommand == "ACK":
                                self.send_notice(
                                    f"Capabilities negotiated with server: {', '.join(self.caps_enabled)}"
                                )
                            elif subcommand == "NAK":
                                self.send_notice("Capabilities request was rejected.")
                        else:
                            self.send_notice("No capabilities requested.")
"""

CAP_HELPER_ANCHOR = "    async def cmd_caps(self, args) -> None:"

CAP_HELPER = """    async def _cap_exchange(self, subcommand, *args):
        # Register the collector before sending. A multi-line CAP reply arrives in a
        # single burst, and expect() only reports the last event of such a burst, so
        # every capability from the earlier lines would be lost.
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        tokens = []

        def collect(connection, event):
            if future.done():
                return

            params = event.arguments
            if not params:
                return

            reply = params[0].upper()

            if reply == "NAK":
                future.set_result(("NAK", []))
                return

            expected = "ACK" if subcommand == "REQ" else subcommand
            if reply != expected:
                return

            more = len(params) > 2 and params[1] == "*"
            chunk = params[2] if more else (params[1] if len(params) > 1 else "")
            tokens.extend(chunk.split())

            if not more:
                future.set_result((reply, tokens))

        self.conn.add_global_handler("cap", collect, -100)
        try:
            self.conn.cap(subcommand, *args)
            return await asyncio.wait_for(future, 10)
        finally:
            self.conn.remove_global_handler("cap", collect)

    async def cmd_caps(self, args) -> None:"""


def patch_caps():
    replace_once("heisenbridge/network_room.py", CAP_OLD, CAP_NEW, "0001-cap-multiline-and-values")
    replace_once("heisenbridge/network_room.py", CAP_HELPER_ANCHOR, CAP_HELPER, "0001-cap-read-helper")


def main():
    patch_caps()
    print("all patches applied")


if __name__ == "__main__":
    main()
