"""Read-only disk identity checks, repeated by each receiving account."""

import json
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
    record = inspect(cfg["mount"])
    if (
        record["mount"] != cfg["mount"]
        or record["filesystem"] != "ext4"
        or not record["writable"]
    ):
        raise ValueError(
            "É necessário um destino ext4 montado exatamente no caminho escolhido, em leitura/escrita."
        )
    if record["uuid"].lower() != cfg["uuid"].lower() or not record["uuid"]:
        raise ValueError("O UUID do disco não corresponde. A receção fica bloqueada.")
    free = shutil.disk_usage(cfg["mount"]).free
    if free < cfg["min_free_gib"] * 1024**3:
        raise ValueError("O destino não tem o espaço livre mínimo.")
    return free
