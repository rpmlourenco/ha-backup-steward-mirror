import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mirror"))
from aiohttp.test_utils import TestClient, TestServer
from receiver.policy import validate
from receiver.server import application
from receiver.storage import validate_mount

KEY = "ssh-ed25519 " + base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + bytes(32)).decode()
UUID = "11111111-1111-4111-8111-111111111111"


class PolicyTests(unittest.TestCase):
    def test_disabled_defaults(self):
        self.assertFalse(validate({})["enabled"])
        self.assertEqual(validate({})["storage_mode"], "dedicated")

    def test_reject_invalid_sources_and_destinations(self):
        for raw in (
            {"mount": "/config"},
            {"mount": "/media/../config"},
            {"mount": "/media/x/"},
            {"enabled": True},
            {"uuid": "wrong"},
            {"port": True},
            {"storage_mode": "automatic"},
            {"sources": [{"name": "../../etc", "public_key": KEY}]},
            {"sources": [{"name": "immich", "public_key": "restrict " + KEY}]},
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate(raw)

    def test_reject_duplicate_names(self):
        with self.assertRaises(ValueError):
            validate({"sources": [{"name": "immich", "public_key": KEY}] * 2})

    def test_disk_identity_free_space_and_mount_are_mandatory(self):
        cfg = validate({"uuid": UUID})
        good = {
            "mount": "/media/mirror",
            "filesystem": "ext4",
            "writable": True,
            "uuid": UUID,
        }
        for record in (
            dict(good, uuid="wrong"),
            dict(good, mount="/media"),
            dict(good, writable=False),
            dict(good, filesystem="overlay"),
        ):
            with (
                patch("receiver.storage.inspect", return_value=record),
                self.assertRaises(ValueError),
            ):
                validate_mount(cfg)

        with (
            patch("receiver.storage.inspect", return_value=good),
            patch("receiver.storage.shutil.disk_usage") as usage,
        ):
            usage.return_value.free = 0
            with self.assertRaises(ValueError):
                validate_mount(cfg)

    def test_internal_storage_requires_its_explicit_mode_and_pinned_uuid(self):
        internal = {"mount": "/media", "filesystem": "ext4", "writable": True, "uuid": UUID}
        with (
            patch("receiver.storage.inspect", return_value=internal),
            patch("receiver.storage.shutil.disk_usage") as usage,
        ):
            usage.return_value.free = 100 * 1024**3
            self.assertEqual(
                validate_mount(validate({"uuid": UUID, "storage_mode": "internal"})), 100 * 1024**3
            )
            with self.assertRaises(ValueError):
                validate_mount(validate({"uuid": UUID}))
            with self.assertRaises(ValueError):
                validate_mount(
                    validate({"uuid": "22222222-2222-4222-8222-222222222222", "storage_mode": "internal"})
                )

    def test_internal_mode_rejects_a_different_mount_even_with_the_same_uuid(self):
        record = {"mount": "/media/mirror", "filesystem": "ext4", "writable": True, "uuid": UUID}
        with patch("receiver.storage.inspect", return_value=record), self.assertRaises(ValueError):
            validate_mount(validate({"uuid": UUID, "storage_mode": "internal"}))


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingress_and_restart_required_without_starting_receiver(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            with patch.dict("os.environ", {"MIRROR_INGRESS_IP": "127.0.0.1"}):
                async with TestClient(
                    TestServer(
                        application(
                            validate({}),
                            path,
                            lambda port: {
                                "protocol": "steward-mirror-v1",
                                "host_key": KEY,
                                "port": port,
                            },
                        )
                    )
                ) as client:
                    response = await client.put("/v1/config", json={"label": "HA2"})
                    self.assertEqual(response.status, 403)
                    response = await client.put(
                        "/v1/config",
                        json={"label": "HA2"},
                        headers={"X-Steward-UI": "1"},
                    )
                    self.assertEqual(response.status, 200)
                    status = await (await client.get("/v1/status")).json()
                    self.assertTrue(status["restart_required"])
                    self.assertFalse(status["listening"])
                    self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["label"], "HA2")

    async def test_public_identity_and_no_arbitrary_actions(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"MIRROR_INGRESS_IP": "127.0.0.1"}),
        ):
            async with TestClient(
                TestServer(
                    application(
                        validate({}),
                        Path(tmp) / "config.json",
                        lambda port: {"host_key": KEY, "port": port},
                    )
                )
            ) as client:
                data = await (
                    await client.post("/v1/identity", json={}, headers={"X-Steward-UI": "1"})
                ).json()
                self.assertEqual(data["host_key"], KEY)
                self.assertNotIn("private", str(data))
                self.assertEqual((await client.post("/v1/run", json={})).status, 403)


if __name__ == "__main__":
    unittest.main()
