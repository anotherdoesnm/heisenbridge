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
| Error replies | `standard-replies` (FAIL/WARN/NOTE) | readable notices | 0012 |
| Nick parsing | `multi-prefix`, `userhost-in-names` | correct puppet ids and member lists | 0009 |
| Joins | `extended-join` | unchanged handling | 0009 |
| Metadata | `account-tag`, `invite-notify`, `chghost`, `message-tags` | — | 0008 |

Extra fixes that are not IRCv3 but were needed on a modern server:

| Fix | Patch |
|---|---|
| CAP negotiation: multi-line replies and `cap=value` (SASL on UnrealIRCd-family servers) | 0001 |
| De-duplicate the NAMES buffer (`mattf, mattf, mattf`) | 0002 |
| Never merge events carrying `m.relates_to` into one message | 0005 |
| `SPACEICON <url>` sets the managed space avatar | 0013 |

## Not implemented

- `+draft/unreact`: removing an annotation means redacting the reaction event,
  which needs a reaction → event map that the bridge does not keep.
- `draft/chathistory`: backfilling history into Matrix rooms is a large feature
  on its own and was left out rather than half-done.
- `echo-message`, `labeled-response`, `batch` outside multiline: not requested,
  because each one changes the message flow and needs its own handling.

## Notes from the field

- obbyircd accepts `@+draft/redact TAGMSG` but does not relay it to other
  clients, even to those that negotiated `draft/message-redaction`. The
  Matrix → IRC direction works; the IRC → Matrix direction only fires on servers
  that do relay redactions.
- `+draft/react` is relayed normally, so reactions work both ways there.
- SASL on such servers failed upstream because `expect()` returns only the last
  event of a burst, so a multi-line `CAP LS` reply was truncated to its last
  line and `sasl` was filtered out. Patch 0001 registers a collector before
  sending and completes it on the final line.

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

- `SPACEICON <url>` in the network room — set the icon of the managed space from
  an image URL, `SPACEICON -` clears it, `SPACEICON` alone shows the current
  value.
