import json
import asyncio
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock, AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mirror"))
from receiver.activity import Activity, Reader, read
from receiver.telemetry import Formatter
from receiver import telemetry


class ActivityTests(unittest.TestCase):
    def test_bounded_events_and_real_elapsed_time(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("receiver.activity.time.monotonic", return_value=100) as clock,
        ):
            root = Path(tmp)
            worker = Activity("photos", root=root)
            clock.return_value = 162
            worker.tick()
            for _ in range(25):
                worker.event("progress")
            worker.finish(0)
            snapshot = read("photos", root)
            self.assertEqual(snapshot["status"], "success")
            self.assertEqual(snapshot["elapsed_seconds"], 62)
            self.assertEqual(len(snapshot["events"]), 12)
            self.assertEqual(snapshot["events"][-1]["kind"], "receiving_completed")
            next_session = Activity("photos", planning=True, root=root)
            self.assertGreater(next_session.seq, snapshot["events"][-1]["seq"])
            self.assertTrue(
                any(event["kind"] == "receiving_completed" for event in next_session.data["events"])
            )

    def test_activity_text_is_allowlisted_before_logs_or_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "photos.json").write_text(
                json.dumps(
                    {
                        "status": "receiving",
                        "events": [
                            {
                                "seq": 1,
                                "kind": "progress",
                                "time": "2026-11-22T12:00:00+00:00",
                                "message": "token=private-should-not-escape",
                            },
                            {"seq": 2, "kind": "token=private"},
                        ],
                        "password": "private",
                        "bytes": "private",
                    }
                ),
                encoding="utf-8",
            )
            snapshot = read("photos", root)
            self.assertNotIn("private", str(snapshot))
            self.assertEqual(snapshot["events"][0]["message"], "Operação em curso")

    def test_symlinks_and_oversized_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "private"
            private.write_text("fixture", encoding="utf-8")
            (root / "photos.json").symlink_to(private)
            with self.assertRaises(OSError):
                read("photos", root)
            (root / "photos.json").unlink()
            (root / "photos.json").write_text("x" * 65537, encoding="utf-8")
            with self.assertRaises(ValueError):
                read("photos", root)

    def test_missing_worker_is_interrupted_and_partial_reads_keep_last_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Activity("photos", root=root)
            with patch("receiver.activity.stamp", return_value=None):
                self.assertEqual(read("photos", root)["status"], "interrupted")
            snapshot = read("photos", root)
            reader = Reader()
            with patch("receiver.activity.read", side_effect=[snapshot, ValueError("partial JSON")]):
                self.assertEqual(reader.get("photos"), reader.get("photos"))

    def test_log_timestamp_contains_date_time_and_explicit_offset(self):
        record = logging.LogRecord("mirror", logging.INFO, "", 0, "Receção iniciada", (), None)
        record.created = 1795348800
        line = Formatter("Europe/Madrid").format(record)
        self.assertRegex(line, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+01:00 INFO \[mirror\]")


class MonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_monitor_emits_new_events_once(self):
        baseline = {"status": "waiting", "events": []}
        snapshot = {
            "status": "receiving",
            "events": [{"seq": 1, "kind": "receiving_started", "message": "Receção iniciada"}],
        }
        reader = Mock()
        reader.get.side_effect = [baseline, snapshot, snapshot]
        with (
            patch("receiver.telemetry.Reader", return_value=reader),
            patch(
                "receiver.telemetry.asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError])
            ),
            patch("receiver.telemetry.logging.log") as log,
        ):
            with self.assertRaises(asyncio.CancelledError):
                await telemetry.monitor({"sources": [{"name": "photos"}]})
        self.assertEqual(log.call_count, 1)
        self.assertIn("Receção iniciada", log.call_args.args)

    async def test_ssh_diagnostics_never_echo_private_text(self):
        process = Mock()
        process.stderr.readline.side_effect = ["private-ip key=fixture-only\n", ""]
        with patch("receiver.telemetry.logging.error") as log:
            await telemetry.ssh_errors(process)
        self.assertEqual(log.call_count, 1)
        self.assertNotIn("fixture-only", str(log.call_args))
