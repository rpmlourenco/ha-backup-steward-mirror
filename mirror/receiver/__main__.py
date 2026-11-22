import asyncio
import json
import logging
from pathlib import Path
import signal
from aiohttp import web

from .policy import validate
from .server import application
from .service import identity, start
from . import telemetry


async def main():
    path = Path("/data/mirror/config.json")
    options = path if path.exists() else Path("/data/options.json")
    cfg = validate(json.loads(options.read_text(encoding="utf-8")) if options.exists() else {})
    telemetry.configure(cfg["timezone"])
    logging.info(
        "A iniciar Data Steward Mirror; fuso=%s; armazenamento=%s", cfg["timezone"], cfg["storage_mode"]
    )
    process, error = None, None
    if cfg["enabled"]:
        try:
            process = start(cfg)
        except Exception:
            error = "Receção bloqueada. Confirma montagem ext4, UUID, espaço e permissões das pastas."
            logging.error(error)
    runner = web.AppRunner(application(cfg, path, identity, process, error), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8099).start()
    logging.info(
        "Data Steward Mirror pronto; receção %s",
        "ativa" if process else "desativada/bloqueada",
    )
    stopped = asyncio.Event()
    activity_monitor = asyncio.create_task(telemetry.monitor(cfg))
    ssh_log = asyncio.create_task(telemetry.ssh_errors(process)) if process else None
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stopped.set)
    try:
        await stopped.wait()
    finally:
        activity_monitor.cancel()
        await asyncio.gather(activity_monitor, return_exceptions=True)
        if process and process.poll() is None:
            process.terminate()
            await asyncio.to_thread(process.wait, 15)
        if ssh_log:
            await asyncio.gather(ssh_log, return_exceptions=True)
            process.stderr.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
