# Local validation — 2026-11-22

Version 0.1.0, experimental. Not installed on the user's HA; hardware acceptance remains pending.

- Six receiver unit tests pass: disabled defaults, schema/keys/paths, duplicate
  origins, ext4 mount/UUID/space guards, ingress authentication and saved-versus-live
  configuration with an explicit restart notice.
- Real OpenSSH/rsync acceptance passes inside one ephemeral container: key auth,
  read-only probe, dry-run, first copy, updates, deletions, confined paths, denied
  shell/pull commands and rejected server key mismatch. The sender is the actual
  L4 module from the companion repository. Only the disk UUID layer is mocked.
- Chrome acceptance passes with fake HTTP responses, desktop/mobile screenshots,
  public pairing import/export, saving, restart notice and offline control locks.
- Final Docker images build for amd64 and aarch64. Python lint passes.
- The companion Steward passes 192 unit tests, its three browser suites and the
  official isolated Home Assistant 2026.10.3 integration smoke (20 unchanged entities).

Pending manual acceptance: HAOS app installation, nonprivileged UUID visibility,
disk permissions, published SSH port, direct LAN/WAN connectivity, real throughput,
application-consistent input preparation and recovery of a representative sample.
No HA credentials, real disks, host devices or HA configuration were mapped into
the test containers. No live transfer or network configuration was performed.

## 0.1.1 — explicit internal storage

- Eight unit tests pass, including explicit internal mode, backing UUID mismatch,
  rejection of a different mount and preserved dedicated-disk fail-closed behavior.
- Real SSH/rsync container acceptance and Chrome desktop/mobile setup pass.
- AMD64 and ARM64 images build successfully; Ruff and Git whitespace checks pass.
- Read-only SSH inspection on HA2 confirms `/media` is ext4 on the internal NVMe
  and its UUID is readable as UID 65534 inside the installed app. No mount, restart,
  data transfer or disk write was used for this inspection.
- Internal storage is an explicit option; upgrades retain dedicated mode until chosen.

## 0.1.2 — timestamped logs and receiving activity

- 15 isolated unit tests pass, including timestamp offsets, bounded activity,
  continued event sequences, worker interruption, partial snapshots and safe log
  messages without raw SSH diagnostics.
- Real SSH/rsync container acceptance passes: probe, dry-run, first copy, updates,
  deletions, confinement and host-key pinning. Tests confirm planning/receiving
  activity and parse real sender progress; only the filesystem UUID is mocked.
- Chrome desktop/mobile setup and receiving-activity checks pass with fake data.
- AMD64/ARM64 builds, Ruff and Git whitespace checks pass.
- No live HA access, configuration edits, restarts or transfer operations were
  performed. The current user-started backup remains untouched.
