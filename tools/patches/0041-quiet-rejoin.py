# 0041 — stop announcing the join burst on every reconnect
#
# Every reconnect (and every bridge restart) made the server replay the state of
# each channel, and the bridge posted all of it as new messages:
#
#   Joined #bots as doesnm (...) / Topic is '...'
#   Topic set by mattf!~u@... at Fri Oct 10 ...
#   Current channel modes: +nHP 1000:1d
#   Channel was created at ...
#
# Rooms restored from account data are already known to the user, so the burst
# is swallowed for a short window after a reconnect. A fresh room still
# announces itself, and a real topic change later is still shown.
#
# Voice and stream channels (`^`, `$`) are joined by the widget rather than by
# hand, so their join/leave notices are dropped entirely.
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


IMPORT_OLD = "import asyncio\nimport html\nimport logging\n"
IMPORT_NEW = "import asyncio\nimport html\nimport logging\nimport time\n"

CLASS_OLD = "class ChannelRoom(PrivateRoom):\n    key: Optional[str]"
CLASS_NEW = """class ChannelRoom(PrivateRoom):
    # how long after a reconnect the join burst is swallowed: the user has seen
    # the topic, the modes and the member list already
    QUIET_AFTER_JOIN = 30.0

    key: Optional[str]"""

POST_OLD = """    async def post_init(self) -> None:
        await super().post_init()
        await self.ensure_voice_widget()
"""

POST_NEW = """    async def post_init(self) -> None:
        await super().post_init()

        # a room restored from account data is already known to the user, so the
        # next connect is a reconnect and must not replay the channel state
        self.joined_once = True
        self.quiet_until = time.time() + self.QUIET_AFTER_JOIN

        await self.ensure_voice_widget()

    def _quiet(self) -> bool:
        return time.time() < getattr(self, "quiet_until", 0.0)
"""

JOIN_OLD = """        # we don't need to sync ourself
        if conn.real_nickname == event.source.nick:
            self.send_notice(f"Joined {event.target} as {event.source.nick} ({event.source.userhost})")
"""

JOIN_NEW = """        # we don't need to sync ourself
        if conn.real_nickname == event.source.nick:
            rejoin = getattr(self, "joined_once", False)
            self.joined_once = True
            self.quiet_until = time.time() + self.QUIET_AFTER_JOIN if rejoin else 0.0

            # voice and stream channels are joined by the widget, not by hand,
            # so announcing every session is noise
            if not rejoin and self.name[:1] not in ("^", "$"):
                self.send_notice(f"Joined {event.target} as {event.source.nick} ({event.source.userhost})")
"""

PART_OLD = """        if conn.real_nickname == event.source.nick:
            # immediately dequeue all future events
            conn.remove_tag(event.target.lower())

            self.send_notice_html(
"""

PART_NEW = """        if conn.real_nickname == event.source.nick:
            # immediately dequeue all future events
            conn.remove_tag(event.target.lower())

            # the voice widget leaves on its own, there is nothing to rejoin by hand
            if self.name[:1] in ("^", "$"):
                return

            self.send_notice_html(
"""

CURRENTTOPIC_OLD = """    def on_currenttopic(self, conn, event) -> None:
        (plain, formatted) = parse_irc_formatting(event.arguments[1])
        self.send_notice(f"Topic is '{plain}'")
        self.set_topic(plain)
"""

CURRENTTOPIC_NEW = """    def on_currenttopic(self, conn, event) -> None:
        (plain, formatted) = parse_irc_formatting(event.arguments[1])

        if not self._quiet():
            self.send_notice(f"Topic is '{plain}'")

        self.set_topic(plain)
"""

TOPICINFO_OLD = """        (plain, formatted) = parse_irc_formatting(event.arguments[1])
        self.send_notice(f"Topic set by {plain} at {settime}")
"""

TOPICINFO_NEW = """        (plain, formatted) = parse_irc_formatting(event.arguments[1])

        if not self._quiet():
            self.send_notice(f"Topic set by {plain} at {settime}")
"""

TOPIC_OLD = """    def on_topic(self, conn, event) -> None:
        self.send_notice("{} changed the topic".format(event.source.nick))
"""

TOPIC_NEW = """    def on_topic(self, conn, event) -> None:
        if not self._quiet():
            self.send_notice("{} changed the topic".format(event.source.nick))
"""

CHANNELCREATE_OLD = """    def on_channelcreate(self, conn, event) -> None:
        created = unix_to_local(event.arguments[1])
        self.send_notice(f"Channel was created at {created}")
"""

CHANNELCREATE_NEW = """    def on_channelcreate(self, conn, event) -> None:
        created = unix_to_local(event.arguments[1])

        if not self._quiet():
            self.send_notice(f"Channel was created at {created}")
"""

MODEIS_OLD = """    def on_channelmodeis(self, conn, event) -> None:
        modes = list(event.arguments)
        modes.pop(0)

        self.send_notice(f"Current channel modes: {' '.join(modes)}")
"""

MODEIS_NEW = """    def on_channelmodeis(self, conn, event) -> None:
        modes = list(event.arguments)
        modes.pop(0)

        if not self._quiet():
            self.send_notice(f"Current channel modes: {' '.join(modes)}")
"""

NOTICE_OLD = """    def on_privnotice(self, conn, event) -> None:
        if self.network is None:
            return
"""

NOTICE_NEW = """    def on_privnotice(self, conn, event) -> None:
        if self.network is None or self._quiet():
            return
"""


def main():
    replace_once(CHAN, IMPORT_OLD, IMPORT_NEW, "quiet-import")
    replace_once(CHAN, CLASS_OLD, CLASS_NEW, "quiet-class")
    replace_once(CHAN, POST_OLD, POST_NEW, "quiet-post-init")
    replace_once(CHAN, JOIN_OLD, JOIN_NEW, "quiet-join")
    replace_once(CHAN, PART_OLD, PART_NEW, "quiet-part")
    replace_once(CHAN, CURRENTTOPIC_OLD, CURRENTTOPIC_NEW, "quiet-currenttopic")
    replace_once(CHAN, TOPICINFO_OLD, TOPICINFO_NEW, "quiet-topicinfo")
    replace_once(CHAN, TOPIC_OLD, TOPIC_NEW, "quiet-topic")
    replace_once(CHAN, CHANNELCREATE_OLD, CHANNELCREATE_NEW, "quiet-channelcreate")
    replace_once(CHAN, MODEIS_OLD, MODEIS_NEW, "quiet-modeis")
    replace_once(CHAN, NOTICE_OLD, NOTICE_NEW, "quiet-notice")


if __name__ == "__main__":
    main()
