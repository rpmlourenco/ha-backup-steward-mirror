## 0.1.0

- Initial experimental rsync/SSH receiver with guided ingress configuration.
- Disabled by default; Ed25519 keys, per-source accounts and pinned destination identity.
- Confined write-only rsync, filesystem UUID/free-space guards and explicit restart notice.
- Unit, browser and real SSH/rsync container tests; no installation or live transfer.
