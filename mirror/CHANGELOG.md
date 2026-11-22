## 0.1.2

- Add ISO date/time/offset to app and transfer-session logs, with configurable timezone.
- Show per-source phase, start/update time, elapsed duration and bounded dated events in the UI.
- Distinguish dry-run comparisons from reception; detect an interrupted worker without scanning data.
- Keep rsync data descriptors direct; detailed byte/rate/ETA counters remain on the sender.

## 0.1.1

- Add explicit internal HAOS/NVMe storage mode with pinned backing filesystem UUID.
- Discover internal storage in guided setup; create only the confined receiver folder on activation.
- Preserve exact-mount validation for dedicated disks; no fallback between storage modes.

## 0.1.0

- Initial experimental rsync/SSH receiver with guided ingress configuration.
- Disabled by default; Ed25519 keys, per-source accounts and pinned destination identity.
- Confined write-only rsync, filesystem UUID/free-space guards and explicit restart notice.
- Unit, browser and real SSH/rsync container tests; no installation or live transfer.
