# Data Steward Mirror development

- Repository implementation does not authorize installation, live transfers, service calls, network changes or disk operations.
- Direct rsync over SSH only; key authentication, strict server identity and confined per-source receiving accounts.
- Disabled by default. No passwords, shell access, forwarding, HA API access or host access for the receiver.
- Never expose private keys or authenticated URLs. Only public pairing information may be exported.
- Keep all machine identifiers configurable. Validate destination filesystem identity before every transfer.
- Tests use temporary fixtures and isolated containers only. Never map real media, HA configuration or hardware.
- No commit, publish or deployment unless explicitly requested.
