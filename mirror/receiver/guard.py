"""Forced SSH command: one account, one confined rsync destination."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from .policy import confined_root, validate
from .storage import validate_mount


def run(name):
    cfg = validate(
        json.loads(Path("/run/mirror/policy.json").read_text(encoding="utf-8"))
    )
    if not cfg["enabled"] or name not in {item["name"] for item in cfg["sources"]}:
        raise ValueError("Receção não autorizada.")
    free = validate_mount(cfg)
    root = confined_root(cfg, name)
    if not root.is_dir() or root.stat().st_uid != os.getuid():
        raise ValueError("Identidade da pasta de receção inválida.")
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    if command == "mirror-probe":
        print(
            json.dumps(
                {
                    "protocol": "steward-mirror-v1",
                    "name": name,
                    "uuid": cfg["uuid"],
                    "free_bytes": free,
                }
            )
        )
        return 0
    if not command.startswith("rsync --server ") or "--sender" in command.split():
        raise ValueError("Só é permitida receção rsync.")
    with open(f"/run/mirror/locks/{name}", "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        activity = Path(f"/run/mirror/activity/{name}.json")
        activity.write_text(
            json.dumps(
                {"status": "receiving", "time": datetime.now(timezone.utc).isoformat()}
            ),
            encoding="utf-8",
        )
        # Upstream parser validates every rsync argument; no shell interpolation.
        process = subprocess.run(
            [sys.executable, "/usr/bin/rrsync", "-wo", "-munge", str(root)], check=False
        )
        activity.write_text(
            json.dumps(
                {
                    "status": "success" if process.returncode == 0 else "failed",
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        return process.returncode


if __name__ == "__main__":
    try:
        sys.exit(run(sys.argv[1]))
    except Exception:
        print(
            "Receção bloqueada: verifica destino, UUID, permissões e execução concorrente.",
            file=sys.stderr,
        )
        sys.exit(1)
