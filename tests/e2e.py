"""Real SSH/rsync, ephemeral container files only. Mount identity is mocked explicitly.

Run inside the receiver image with BOTH source repositories mounted read-only.
No host disks, device files, HA paths, HA APIs or network ports are mapped.
"""

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, "/sender/backup_steward")
sys.path.insert(0, "/app")
from receiver import service
from receiver.policy import validate
from steward.l4 import Mirror, Plan, execute, rsync_args, ssh_args
from steward.config import validate as sender_config
from steward.engine import Engine
from steward.state import State
from unittest.mock import AsyncMock


async def main():
    Path("/media").mkdir(exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix="mirror_test_", dir="/media") as destination,
        tempfile.TemporaryDirectory() as tmp,
    ):
        root = Path(tmp)
        os.chmod(destination, 0o755)
        source = root / "source"
        source.mkdir()
        (source / "photo.jpg").write_bytes(b"original-photo" * 10000)
        (source / "document.txt").write_text("primeira versão", encoding="utf-8")
        engine = Engine(
            sender_config(
                {
                    "l4": {
                        "sources": [
                            {
                                "source": "/media/immich",
                                "name": "immich",
                                "uuid": "11111111-1111-4111-8111-111111111111",
                            }
                        ]
                    }
                }
            ),
            State(root / "state"),
            AsyncMock(),
        )
        mirror = Mirror(engine)
        pairing = await mirror.pairing()
        cfg = validate(
            {
                "enabled": True,
                "mount": destination,
                "uuid": "11111111-1111-4111-8111-111111111111",
                "sources": pairing["sources"],
                "min_free_gib": 1,
            }
        )
        # Only disk identity is mocked: actual SSH account/key/forced command,
        # confinement, receiver filesystem and rsync data path are exercised.
        with patch("receiver.service.validate_mount", return_value=100 * 1024**3):
            process = service.start(cfg)
        process.terminate()
        process.wait(5)
        wrapper = root / "guard.py"
        # sshd accounts cannot traverse TemporaryDirectory's default 0700 parent.
        os.chmod(root, 0o755)
        wrapper.write_text(
            'import sys\nsys.path.insert(0,"/app")\nfrom receiver import guard\nguard.validate_mount=lambda cfg:100*1024**3\nsys.exit(guard.run(sys.argv[1]))\n',
            encoding="utf-8",
        )
        config_path = service.RUN / "sshd_config"
        text = config_path.read_text(encoding="utf-8").replace("/app/receive.py", str(wrapper))
        config_path.write_text(text, encoding="utf-8")
        process = subprocess.Popen(["/usr/sbin/sshd", "-D", "-e", "-f", str(config_path)])
        try:
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", 2222), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.05)
            identity = service.identity(2222)
            sender = dict(
                engine.cfg["l4"],
                host="127.0.0.1",
                host_key=identity["host_key"],
                destination_uuid=cfg["uuid"],
                min_free_gib=1,
            )
            mirror.prepare(sender)
            item = dict(sender["sources"][0], source=str(source))
            data = await mirror.probe(sender, item)
            assert data["name"] == "immich"
            plan = Plan()
            try:
                await execute(
                    rsync_args(sender, mirror.directory, item, dry=True),
                    progress=plan.feed,
                )
            except ValueError:
                diagnostic = subprocess.run(
                    rsync_args(sender, mirror.directory, item, dry=True),
                    capture_output=True,
                )
                print(diagnostic.stderr.decode("utf-8", errors="replace"))
                raise
            plan.finish()
            assert plan.bytes > 0
            target = Path(destination) / "immich"
            assert not (target / "photo.jpg").exists(), "dry run wrote a file"
            snapshot = json.loads(Path("/run/mirror/activity/immich.json").read_text(encoding="utf-8"))
            assert snapshot["operation"] == "planning"
            from steward.l4_progress import Progress

            sender_progress = Progress()
            await execute(rsync_args(sender, mirror.directory, item), progress=sender_progress.feed)
            assert sender_progress.finish()["bytes"] > 0
            snapshot = json.loads(Path("/run/mirror/activity/immich.json").read_text(encoding="utf-8"))
            assert snapshot["operation"] == "receiving" and snapshot["status"] == "success"
            assert isinstance(snapshot["elapsed_seconds"], int)
            assert snapshot["events"][-1]["kind"] == "receiving_completed"
            assert (target / "photo.jpg").read_bytes() == (source / "photo.jpg").read_bytes()
            (source / "document.txt").write_text("segunda versão mais longa", encoding="utf-8")
            (source / "photo.jpg").unlink()
            await execute(rsync_args(sender, mirror.directory, item))
            assert not (target / "photo.jpg").exists()
            assert (target / "document.txt").read_text(encoding="utf-8") == "segunda versão mais longa"
            # Arbitrary commands and pull/read mode are refused.
            for command in (
                "touch /tmp/mirror_escape",
                "rsync --server --sender -rt . ./",
            ):
                try:
                    await execute(
                        ssh_args(sender, mirror.directory, "immich") + ["mirror_immich@127.0.0.1", command]
                    )
                except ValueError:
                    pass
                else:
                    raise AssertionError("unsafe SSH command accepted")
            assert not Path("/tmp/mirror_escape").exists()
            escaped = rsync_args(sender, mirror.directory, item)
            escaped[-1] = "mirror_immich@127.0.0.1:../../outside/"
            try:
                await execute(escaped)
            except ValueError:
                pass
            else:
                raise AssertionError("path traversal accepted")
            # Pinning must reject a different, syntactically valid host key.
            wrong = root / "wrong"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(wrong)],
                check=True,
            )
            wrong_public = (
                subprocess.run(
                    ["ssh-keygen", "-y", "-f", str(wrong)],
                    capture_output=True,
                    check=True,
                )
                .stdout.decode()
                .strip()
            )
            mirror.prepare(dict(sender, host_key=wrong_public))
            try:
                await execute(
                    ssh_args(sender, mirror.directory, "immich") + ["mirror_immich@127.0.0.1", "mirror-probe"]
                )
            except ValueError:
                pass
            else:
                raise AssertionError("host identity mismatch accepted")
            print(
                "PASS: actual SSH key auth, probe, dry-run, initial copy, update, deletion, confinement, shell/pull rejection and host-key pinning; filesystem UUID mocked."
            )
        finally:
            process.terminate()
            process.wait(5)


asyncio.run(main())
