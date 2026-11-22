"""Bounded per-source telemetry; never treat worker text as a log message."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

ROOT = Path("/run/mirror/activity")
MESSAGES = {
    "planning_started": "Comparação iniciada",
    "planning_completed": "Comparação concluída",
    "receiving_started": "Receção iniciada",
    "receiving_completed": "Receção concluída",
    "progress": "Operação em curso",
    "failed": "Operação falhou",
    "interrupted": "Operação interrompida",
}
NUMBERS = ("elapsed_seconds",)


def now():
    return datetime.now(timezone.utc).isoformat()


def stamp(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="ascii").rpartition(")")[2].split()[19]
    except OSError, IndexError:
        return None


class Activity:
    def __init__(self, name, planning=False, root=ROOT):
        self.path = root / (name + ".json")
        self.operation = "planning" if planning else "receiving"
        self.started = time.monotonic()
        self.written = self.logged = self.started
        try:
            previous = read(name, root).get("events", [])
        except OSError, ValueError, TypeError:
            previous = []
        self.seq = max((event["seq"] for event in previous), default=0)
        self.data = {
            "session": uuid.uuid4().hex,
            "pid": os.getpid(),
            "stamp": stamp(os.getpid()),
            "status": self.operation,
            "operation": self.operation,
            "started_at": now(),
            "events": previous[-12:],
        }
        self.event(self.operation + "_started")

    def save(self):
        self.data.update(time=now(), elapsed_seconds=int(time.monotonic() - self.started))
        # Root owns the parent and the fixed file; the receiving account cannot
        # rename/symlink it. Readers retain the last valid bounded snapshot.
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        self.written = time.monotonic()

    def event(self, kind):
        self.data["elapsed_seconds"] = int(time.monotonic() - self.started)
        self.seq += 1
        event = {"seq": self.seq, "kind": kind, "time": now()}
        event.update({key: self.data.get(key) for key in NUMBERS})
        self.data["events"] = self.data["events"][-11:] + [event]
        self.save()
        self.logged = time.monotonic()

    def tick(self, force=False):
        if time.monotonic() - self.logged >= 60:
            self.event("progress")
        elif force or time.monotonic() - self.written >= 2:
            self.save()

    def finish(self, code):
        self.data.update(
            status="success" if code == 0 else "interrupted" if code < 0 else "failed",
            exit_code=code,
            finished_at=now(),
        )
        self.event(self.operation + "_completed" if code == 0 else "interrupted" if code < 0 else "failed")


def date(value):
    try:
        if not isinstance(value, str) or len(value) > 40 or datetime.fromisoformat(value).tzinfo is None:
            return None
        return value
    except ValueError:
        return None


def metrics(raw):
    result = {}
    for key in NUMBERS:
        value = raw.get(key)
        if type(value) is int and 0 <= value <= (100 if key == "percent" else 10**18):
            result[key] = value
    return result


def read(name, root=ROOT):
    fd = os.open(root / (name + ".json"), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Invalid activity file")
        content = stream.read(65537)
    if len(content) > 65536:
        raise ValueError("Oversized activity file")
    raw = json.loads(content.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid activity snapshot")
    session = raw.get("session", "")
    result = {
        "name": name,
        "status": raw.get("status")
        if raw.get("status") in ("waiting", "planning", "receiving", "success", "failed", "interrupted")
        else "waiting",
        "operation": "planning" if raw.get("operation") == "planning" else "receiving",
        "session": session if isinstance(session, str) and re.fullmatch(r"[a-f0-9]{32}", session) else "",
        "events": [],
        **metrics(raw),
    }
    for key in ("time", "started_at", "finished_at"):
        result[key] = date(raw.get(key))
    raw_events = raw.get("events", [])
    for item in raw_events[-12:] if isinstance(raw_events, list) else []:
        if not isinstance(item, dict) or item.get("kind") not in MESSAGES or type(item.get("seq")) is not int:
            continue
        result["events"].append(
            {
                "seq": item["seq"],
                "kind": item["kind"],
                "message": MESSAGES[item["kind"]],
                "time": date(item.get("time")),
                **metrics(item),
            }
        )
    if result["status"] in ("receiving", "planning") and type(raw.get("pid")) is int and raw.get("stamp"):
        if stamp(raw["pid"]) != raw["stamp"]:
            result["status"] = "interrupted"
            result["events"].append(
                {
                    "seq": max((e["seq"] for e in result["events"]), default=0) + 1,
                    "kind": "interrupted",
                    "message": MESSAGES["interrupted"],
                    "time": now(),
                }
            )
    return result


class Reader:
    def __init__(self):
        self.cache = {}

    def get(self, name):
        try:
            self.cache[name] = read(name)
        except OSError, ValueError, TypeError:
            pass
        return self.cache.get(name, {"name": name, "status": "waiting", "events": []})
