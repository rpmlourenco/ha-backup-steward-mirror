"""Timestamped app-console logs. Worker events are mapped to fixed messages."""

import asyncio
from datetime import datetime
import logging
import sys
from zoneinfo import ZoneInfo

from .activity import Reader


class Formatter(logging.Formatter):
    def __init__(self, zone):
        super().__init__("%(asctime)s %(levelname)s [mirror] %(message)s")
        self.zone = ZoneInfo(zone)

    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, self.zone).isoformat(timespec="seconds")


def configure(zone):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(Formatter(zone))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


async def monitor(cfg):
    reader, seen = Reader(), {}
    for source in cfg["sources"]:
        item = reader.get(source["name"])
        seen[source["name"]] = max((event["seq"] for event in item["events"]), default=0)
        if item["status"] == "interrupted":
            logging.warning("%s: operação anterior interrompida", source["name"])
    while True:
        for source in cfg["sources"]:
            item = reader.get(source["name"])
            for event in item["events"]:
                key = source["name"]
                if event["seq"] <= seen.get(key, 0):
                    continue
                seen[key] = event["seq"]
                elapsed = event.get("elapsed_seconds")
                detail = f"; tempo decorrido={elapsed}s" if elapsed is not None else ""
                level = (
                    logging.ERROR
                    if event["kind"] == "failed"
                    else logging.WARNING
                    if event["kind"] == "interrupted"
                    else logging.INFO
                )
                logging.log(level, "%s: %s%s", source["name"], event["message"], detail)
        await asyncio.sleep(1)


async def ssh_errors(process):
    while await asyncio.to_thread(process.stderr.readline):
        # Do not echo SSH's raw text (usernames, addresses, paths or key data).
        logging.error(
            "Servidor SSH reportou uma ligação ou sessão com erro; confirma a rede e as chaves no emissor."
        )
