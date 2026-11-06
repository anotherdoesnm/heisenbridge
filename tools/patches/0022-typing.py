# 0022 — typing indicators both ways (IRCv3 +typing client tag)
#
# The `typing` client tag is a client-only tag on TAGMSG:
#
#   @+typing=active :nick!user@host TAGMSG #channel
#
# It only needs `message-tags`, which the bridge already negotiates, and servers
# such as obbyircd relay it. Map it to Matrix typing notifications and back:
#
#   IRC  +typing=active/paused/done  ->  m.typing (6s / 6s / 0s)
#   Matrix m.typing for the user     ->  @+typing=active TAGMSG <target>
#
# The IRC side asks for at most one notification per target every 3 seconds, so
# outgoing notifications are throttled.
#
# Standalone patch: run it from the repository root, or let tools/apply_patches.py
# pick it up at build time. Anchored rewrites fail loudly when upstream moves.
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PM = "heisenbridge/private_room.py"


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


REGISTER_OLD = """        self.mx_register("m.room.message", self.on_mx_message)
        self.mx_register("m.room.redaction", self.on_mx_redaction)
        self.mx_register("m.reaction", self.on_mx_reaction)
"""

REGISTER_NEW = """        self.typing_sent = 0

        self.mx_register("m.room.message", self.on_mx_message)
        self.mx_register("m.room.redaction", self.on_mx_redaction)
        self.mx_register("m.reaction", self.on_mx_reaction)
        self.mx_register("m.typing", self.on_mx_typing)
"""

TAGMSG_OLD = """        target = None
        redact = None
        react = None

        for tag in event.tags or []:
            if tag["key"] == "+draft/reply":
                target = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/redact":
                redact = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/react":
                react = tag["value"]

        if redact is not None:
"""

TAGMSG_NEW = """        target = None
        redact = None
        react = None
        typing = None

        for tag in event.tags or []:
            if tag["key"] == "+draft/reply":
                target = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/redact":
                redact = self.msgids.get(tag["value"])
            elif tag["key"] == "+draft/react":
                react = tag["value"]
            elif tag["key"] == "+typing":
                typing = tag["value"]

        if typing is not None:
            irc_user_id = self.serv.irc_user_id(self.network.name, event.source.nick)
            # active and paused both keep the indicator alive, done clears it
            timeout = 0 if typing == "done" else 6000
            asyncio.ensure_future(self.az.intent.user(irc_user_id).set_typing(self.id, timeout))

        if redact is not None:
"""

METHOD_OLD = """    async def on_mx_redaction(self, event) -> None:
"""

METHOD_NEW = """    async def on_mx_typing(self, event) -> None:
        if self.network is None or self.network.conn is None or not self.network.conn.connected:
            return

        if "message-tags" not in (self.network.caps_enabled or []):
            return

        if self.user_id not in (event.content.user_ids or []):
            return

        # the typing tag asks for at most one notification per 3 seconds per target
        now = asyncio.get_running_loop().time()
        if now - self.typing_sent < 3:
            return

        self.typing_sent = now
        self.network.conn.send_items("@+typing=active TAGMSG", self.name)

    async def on_mx_redaction(self, event) -> None:
"""


def main():
    replace_once(PM, REGISTER_OLD, REGISTER_NEW, "typing-register")
    replace_once(PM, TAGMSG_OLD, TAGMSG_NEW, "typing-incoming")
    replace_once(PM, METHOD_OLD, METHOD_NEW, "typing-outgoing")


if __name__ == "__main__":
    main()
