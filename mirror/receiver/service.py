"""Unprivileged SSH receiver, without host or HA API access."""

import json
import os
from pathlib import Path
import pwd
import subprocess
import zlib

from .policy import confined_root
from .storage import validate_mount

DATA = Path("/data/mirror")
RUN = Path("/run/mirror")


def identity(port):
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(DATA, 0o700)
    key = DATA / "host_ed25519"
    if not key.exists():
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(key)],
            check=True,
        )
    os.chmod(key, 0o600)
    public = (
        subprocess.run(["ssh-keygen", "-y", "-f", str(key)], check=True, capture_output=True)
        .stdout.decode("utf-8")
        .strip()
    )
    return {"protocol": "steward-mirror-v1", "port": port, "host_key": public}


def start(cfg):
    validate_mount(cfg)
    root = Path(cfg["mount"])
    if cfg.get("storage_mode") == "internal" and not root.exists():
        # Only after confirming the explicitly selected /media backing UUID.
        root.mkdir(mode=0o755)
    confined_root(cfg, cfg["sources"][0]["name"])
    parent = Path(cfg["mount"]).stat()
    if parent.st_uid != 0 or parent.st_mode & 0o022 or parent.st_mode & 0o005 != 0o005:
        raise ValueError(
            "A raiz do disco deve pertencer a root, permitir leitura/travessia e impedir escrita de outros utilizadores."
        )
    identity(cfg["port"])
    RUN.mkdir(mode=0o755, exist_ok=True)
    for name in ("keys", "locks", "activity"):
        (RUN / name).mkdir(mode=0o755, exist_ok=True)
    (RUN / "policy.json").write_text(json.dumps(cfg), encoding="utf-8")
    os.chmod(RUN / "policy.json", 0o644)
    for item in cfg["sources"]:
        name = item["name"]
        user = "mirror_" + name
        uid = 20000 + zlib.crc32(name.encode("ascii")) % 30000
        try:
            account = pwd.getpwnam(user)
        except KeyError:
            subprocess.run(
                [
                    "useradd",
                    "--no-create-home",
                    "--uid",
                    str(uid),
                    "--user-group",
                    "--home-dir",
                    "/",
                    "--shell",
                    "/bin/sh",
                    "--password",
                    "*",
                    user,
                ],
                check=True,
                capture_output=True,
            )
            account = pwd.getpwnam(user)
        root = confined_root(cfg, name)
        if not root.exists():
            root.mkdir(mode=0o700)
            os.chown(root, account.pw_uid, account.pw_gid)
        if root.stat().st_uid != account.pw_uid or root.stat().st_mode & 0o022:
            raise ValueError(
                "Uma pasta existente tem proprietário ou permissões incompatíveis. Não foi adotada."
            )
        key = RUN / "keys" / user
        key.write_text("restrict " + item["public_key"] + "\n", encoding="utf-8")
        os.chmod(key, 0o644)
        for path in (RUN / "locks" / name, RUN / "activity" / (name + ".json")):
            path.touch()
            os.chown(path, account.pw_uid, account.pw_gid)
            os.chmod(path, 0o600)
    Path("/run/sshd").mkdir(mode=0o755, exist_ok=True)
    config = """Port 2222
ListenAddress 0.0.0.0
HostKey /data/mirror/host_ed25519
PidFile /run/mirror/sshd.pid
AuthorizedKeysFile /run/mirror/keys/%u
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
PermitRootLogin no
UsePAM no
StrictModes yes
PermitTTY no
DisableForwarding yes
PermitUserRC no
PermitUserEnvironment no
MaxAuthTries 3
LoginGraceTime 20
MaxStartups 5:30:10
LogLevel ERROR
"""
    config += "AllowUsers " + " ".join("mirror_" + i["name"] for i in cfg["sources"]) + "\n"
    for item in cfg["sources"]:
        config += f"\nMatch User mirror_{item['name']}\n    ForceCommand /usr/local/bin/python /app/receive.py {item['name']}\n"
    path = RUN / "sshd_config"
    path.write_text(config, encoding="utf-8")
    subprocess.run(["sshd", "-t", "-f", str(path)], check=True, capture_output=True)
    return subprocess.Popen(["/usr/sbin/sshd", "-D", "-e", "-f", str(path)])
