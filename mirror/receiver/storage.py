"""Read-only disk identity checks, repeated by each receiving account."""

import json
from pathlib import Path
import shutil
import subprocess


def inspect(path):
    result = subprocess.run(
        ["findmnt", "-J", "-T", str(path), "-o", "TARGET,UUID,FSTYPE,OPTIONS"],
        capture_output=True,
        timeout=10,
        check=True,
    )
    record = json.loads(result.stdout.decode("utf-8"))["filesystems"][0]
    return {
        "mount": record["target"],
        "uuid": record.get("uuid") or "",
        "filesystem": record["fstype"],
        "writable": "rw" in record["options"].split(","),
    }


def validate_mount(cfg):
    root = Path(cfg["mount"])
    if root.is_symlink() or root.resolve() != root:
        raise ValueError("O caminho do destino não pode atravessar links simbólicos.")
    internal = cfg.get("storage_mode", "dedicated") == "internal"
    expected = "/media" if internal else cfg["mount"]
    record = inspect(root if root.exists() else expected)
    if record["mount"] != expected or record["filesystem"] != "ext4" or not record["writable"]:
        raise ValueError(
            "A montagem ext4 não corresponde ao tipo de armazenamento escolhido, ou está em leitura apenas."
        )
    if record["uuid"].lower() != cfg["uuid"].lower() or not record["uuid"]:
        raise ValueError("O UUID do disco não corresponde. A receção fica bloqueada.")
    free = shutil.disk_usage(root if root.exists() else expected).free
    if free < cfg["min_free_gib"] * 1024**3:
        raise ValueError("O destino não tem o espaço livre mínimo.")
    return free
