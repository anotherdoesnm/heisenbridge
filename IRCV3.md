# IRCv3 support in this fork

This is a fork of [heisenbridge](https://github.com/hifi/heisenbridge) that adds
IRCv3 support. Upstream is effectively frozen (last merge by the maintainer in
2023), so the changes live here as small, anchored patches in
[`tools/patches/`](tools/patches) that `tools/apply_patches.py` applies to the
pristine upstream tree at build time. Nothing in `heisenbridge/` is modified in
the repository itself, which keeps the delta reviewable and lets a rebase fail
loudly instead of silently shipping an unpatched image.

Images are published to `ghcr.io/anotherdoesnm/heisenbridge` for every push to
`master` (amd64) and for release tags (amd64 + arm64).

## Supported

| Feature | IRC side | Matrix side | Patch |
|---|---|---|---|
| Message ids | `msgid` tag | in-memory `msgid` ↔ event id map | 0003 |
| Replies | `+draft/reply` tag | `m.relates_to.m.in_reply_to` | 0003, 0004 |
| Redactions | `+draft/redact` TAGMSG | `m.room.redaction` | 0006 |
| Reactions | `+draft/react` TAGMSG | `m.reaction` (`m.annotation`) | 0007 |
| Away state | `away-notify` | `m.presence` (`unavailable` + status) | 0010 |
| Multi-line | `draft/multiline` batches | one event with newlines | 0011 |
| Typing | `+typing` client tag | `m.typing` for the puppet | 0022 |
| Error replies | `standard-replies` (FAIL/WARN/NOTE) | readable notices | 0012 |
| Read markers | `draft/read-marker` (MARKREAD) | `m.receipt` when the user posts | 0014 |
| Network icon | `draft/ICON` ISUPPORT token (spec: `draft/network-icon`) | space avatar | 0013, 0015 |
| Metadata | `draft/metadata-2` (`avatar` key) | channel room avatar, puppet profile avatar | 0019 |
| Nick parsing | `multi-prefix`, `userhost-in-names` | correct puppet ids and member lists | 0009 |
| Joins | `extended-join` | unchanged handling | 0009 |
| Extra caps | `account-tag`, `invite-notify`, `chghost`, `message-tags` | — | 0008 |
| Voice | `obsidianirc/voice` (`^` voice, `$` stream) | WebRTC in a room widget | 0023–0039 |

Extra fixes that are not IRCv3 but were needed on a modern server:

| Fix | Patch |
|---|---|
| CAP negotiation: multi-line replies and `cap=value` (SASL on UnrealIRCd-family servers) | 0001 |
| De-duplicate the NAMES buffer (`mattf, mattf, mattf`) | 0002 |
| Never merge events carrying `m.relates_to` into one message | 0005 |
| `SPACEICON <url>` overrides the space avatar on networks without an icon | 0013 |
| State events in room version 12 rooms (mautrix refuses them locally) | 0017 |
| Invites without `is_direct` into an existing DM | 0018 |
| Avatar URL cache that survives a restart | 0020 |
| `MARKREAD` echo shown as a notice in the network room | 0021 |
| Bridge presence stayed offline: `set_presence` was given the user id instead of the state | 0040 |
| Every reconnect replayed the topic, modes and member list as messages | 0041, 0042, 0046 |
| History replay was posted as new messages, including replay nested in multiline batches | 0043, 0047 |
| SIGTERM killed the connection without a QUIT, so the nick could still be taken | 0044 |
| Puppets were kicked with their own intent (`M_FORBIDDEN: You cannot kick yourself`) | 0045 |
| Multiline messages were posted by the bridge account instead of the IRC user | 0048 |

## Not implemented

- `+draft/unreact`: removing an annotation means redacting the reaction event,
  which needs a reaction → event map that the bridge does not keep.
- `draft/chathistory`: backfilling history into Matrix rooms is a large feature
  on its own and was left out rather than half-done.
- `account-tag`: the capability is negotiated but the tag is not surfaced. The only
  sensible Matrix-side mapping would rename puppets to `nick (account)`, which
  breaks pills and mentions, so it is left alone.
- Read markers from IRC to Matrix: a read marker from another user describes their
  own state, and a Matrix receipt cannot be written on behalf of another user.
- `echo-message`, `labeled-response`, `batch` outside multiline: not requested,
  because each one changes the message flow and needs its own handling.
- Typing from Matrix to IRC: appservices never receive ephemeral events
  (`m.typing`, `m.receipt`), so the bridge cannot tell when its user starts
  typing. The other direction works.

## Notes from the field

- obbyircd accepts `@+draft/redact TAGMSG` but does not relay it to other
  clients, even to those that negotiated `draft/message-redaction`. The
  Matrix → IRC direction works; the IRC → Matrix direction only fires on servers
  that do relay redactions.
- `+draft/react` is relayed normally, so reactions work both ways there.
- In `draft/multiline` the message tags (`msgid`, `+draft/reply`) sit on the
  `BATCH` line, not on the individual `PRIVMSG`s, so the bridge reads the sender
  and the reply target from there and only buffers the text.
- `draft/multiline` must be used as the batch type when sending a multiline
  message. `draft/multiline-concat` is a different type (it joins lines without
  separators) and obbyircd answers it with `FAIL BATCH UNKNOWN_TYPE`, after
  which every line goes out as its own PRIVMSG.
- SASL on such servers failed upstream because `expect()` returns only the last
  event of a burst, so a multi-line `CAP LS` reply was truncated to its last
  line and `sasl` was filtered out. Patch 0001 registers a collector before
  sending and completes it on the final line.
- The IRCv3 specification is called "Network Icon" (`draft/network-icon`), but
  the ISUPPORT token it defines is `draft/ICON` (the final, unprefixed name is
  `ICON`). The bridge accepts both spellings and replaces the `{size}` template
  variable with `512`. UnrealIRCd-family servers such as h4ks.com publish the
  token in their `005` burst, which only arrives after registration, so the icon
  is applied on connect rather than at space creation.
- A space restored from account data had no `network` attribute — it was only set
  in `SpaceRoom.create()` — so the `draft/ICON` handler raised `AttributeError`
  after every bridge restart. Patch 0016 keeps the reference in `post_init()` and
  resolves the network defensively in `apply_icon()`.
- UnrealIRCd publishes its capabilities in two bursts and, with
  `draft/chathistory` requested, may wrap a history replay in a `BATCH` of type
  `chathistory`. The bridge advertises the capability so servers do not fall back
  to replaying history as plain PRIVMSGs, and drops such a batch if it comes
  anyway: history is never backfilled into Matrix rooms.
- Parley replays channel history on join as a `BATCH` of type `chathistory`.
  Messages that had several lines come wrapped in a `draft/multiline` batch
  opened *inside* that history batch, so dropping only the outer batch still
  posted them; both are dropped now, together with TAGMSGs (reactions, typing)
  that arrive inside a replay. The bridge advertises `draft/chathistory`, which
  should make a server wait for explicit requests, but Parley sends the fallback
  regardless.
- A reconnect makes the server replay the state of every channel (topic, modes,
  creation time, NAMES). Rooms restored from account data are already known to
  the user, so the bridge swallows that burst for 30 seconds after a reconnect;
  a channel joined for the first time still reports itself.
- Room version 12 (MSC4289) dropped the creator from
  `m.room.power_levels.users`, so mautrix's local power level check saw the
  bridge as power level 0 in rooms the bridge had created itself and dropped
  every topic sync with an `IntentError`. The homeserver still treats the
  creator as an admin, so patch 0017 removes the pre-check and lets the server
  answer.

## Avatars

Two different IRCv3 mechanisms feed the same idea:

- `draft/ICON` in `005` (spec "Network Icon") gives the icon of the whole
  network, which the bridge puts on the managed space.
- `draft/metadata-2` gives per-target metadata. The bridge subscribes to the
  `avatar` key once per connection, so the server pushes the icon of every
  channel it joins and of every user in it, plus updates as they change.

Channel avatars become the Matrix room avatar of the channel room; user avatars
become the puppet's profile avatar. The images are downloaded and re-uploaded to
the homeserver (Matrix needs an mxc URI), and the URL to mxc mapping is kept in
the bridge config so a restart does not upload everything again. Images larger
than 4 MiB are skipped.

`draft/metadata-2` also carries `display-name`, `url` and friends, which are
ignored on purpose: renaming puppets from metadata breaks pills and mentions, and
a "url" key has no obvious place in a Matrix room.

## Files and images

Sending an image, file, audio or video in a channel room makes the bridge post a
public link to the IRC channel (and add a 🔗 reaction on the Matrix side). The
link points at a small proxy inside the bridge, which fetches the media from the
homeserver with the appservice token and streams it back. No extra container is
needed: the same aiohttp app that receives transactions serves
`/_heisenbridge/media/...`.

The feature has to be switched on, because the bridge cannot guess its own public
URL. Put `media_url` in the bridge config (the `irc` account data of the bridge
user) and restart:

```yaml
media_url: https://heisen.doesnmlab.xyz
```

Links then look like
`https://heisen.doesnmlab.xyz/_heisenbridge/media/<server>/<media_id>/<checksum>/<filename>`.
The checksum is an HMAC of the mxc URI keyed with `media_key`, which defaults to
the appservice `hs_token`; a wrong checksum is answered with 403, so the proxy is
not an open relay into the media repository. Media is served with
`Content-Disposition: attachment` and a sandboxing CSP, so browsers download it
instead of rendering it inline.

`--media-proxy` runs the same proxy as a standalone process, for deployments that
do not want to expose the appservice port. It is not required when the bridge is
already reachable over HTTPS.

## Voice

`obsidianirc/voice` (obby) is a small voice and stream protocol on top of IRCv3
client tags: `^` channels are voice rooms, `$` channels are stream-only rooms,
and all signalling is a JSON envelope carried in
`@+obsidianirc/rtc=<json> TAGMSG`.

The bridge relays those TAGMSGs between IRC and a Matrix widget, so a Matrix user
joins a voice channel from the room instead of opening an IRC client. On join the
SFU answers with `joined`, which carries the member list and TURN credentials;
the widget builds a `RTCPeerConnection` from them and offers, and the answer and
ICE candidates come back through the same tag. Media goes straight from the
browser to the SFU — the bridge only moves signalling.

The widget is served by the bridge itself at `/voice/index.html`, from the same
aiohttp app that receives transactions, so no extra container or host is needed.
It is added to `^` and `$` channel rooms automatically, with a per-room token in
the URL (`hmac_sha256(media_key, room_id)[:32]`). The widget presents that token
on the WebSocket at `/voice/ws` and the bridge binds the session to the network
and channel; a wrong or missing token is rejected, so the endpoint is not an open
relay into IRC.

Requirements: the bridge has to be reachable over HTTPS (the client loads the
widget from it) and the IRC network has to support `obsidianirc/voice`. Audio
only — the widget publishes no video, because a video transceiver inflates the
offer past what the SFU accepts and the widget only plays audio anyway.

### The 512 byte trap

`python-irc` refuses to send a line longer than 512 bytes:

```python
if len(bytes) > 512:
    raise MessageTooLong(msg)
```

An SDP offer is about 1.2 KB, so every offer raised `MessageTooLong` inside
`send_raw` and never reached the server, while small ICE candidates went
through. The symptom was a widget stuck at "connecting to SFU" with no error on
either side. Patch 0039 overrides `_prep_message` on the connection: short lines
keep the original path, long ones skip the cap.

## Usage

```sh
docker pull ghcr.io/anotherdoesnm/heisenbridge:latest
```

```yaml
services:
  heisenbridge:
    image: ghcr.io/anotherdoesnm/heisenbridge:latest
```

Commands added by the fork:

- `SPACEICON` in the network room — the managed space avatar comes from the
  `draft/ICON` ISUPPORT token the server publishes (spec `draft/network-icon`);
  the bridge applies it on the first connect and only when the space has no
  avatar yet, so reconnects do not re-upload it. `SPACEICON` alone only reports
  the icon and where it came from, `SPACEICON <url>` applies an explicit image
  URL straight away, and `SPACEICON -` drops the override and re-applies the
  network icon if the network publishes one. The override is worth keeping for
  networks that publish no icon at all.
