"""Forced SSH command: one account, one confined rsync destination."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import shlex
import signal
import time

from .policy import confined_root, validate
from .storage import validate_mount
from .activity import Activity


def run(name):
    cfg = validate(json.loads(Path("/run/mirror/policy.json").read_text(encoding="utf-8")))
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
        options = shlex.split(command)
        options = options[: options.index(".")] if "." in options else options
        planning = any(
            arg == "--dry-run" or (arg.startswith("-") and not arg.startswith("--") and "n" in arg[1:])
            for arg in options
        )
        activity = Activity(name, planning)
        # Upstream parser validates every rsync argument; no shell interpolation.
        process = subprocess.Popen(
            [sys.executable, "/usr/bin/rrsync", "-wo", "-munge", str(root)],
            start_new_session=True,
        )

        def interrupted(signum, frame):
            raise InterruptedError("SSH session interrupted")

        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP)}
        try:
            # Data/protocol descriptors remain directly connected to SSH.
            while process.poll() is None:
                activity.tick()
                time.sleep(0.5)
            code = process.wait()
            activity.finish(code)
            return code
        except BaseException:
            activity.finish(-1)
            raise
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    process.wait()


if __name__ == "__main__":
    try:
        sys.exit(run(sys.argv[1]))
    except Exception:
        print(
            "Receção bloqueada: verifica destino, UUID, permissões e execução concorrente.",
            file=sys.stderr,
        )
        sys.exit(1)
