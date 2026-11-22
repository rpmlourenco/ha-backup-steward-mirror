"""Ingress-only configuration. Saving policy never silently restarts SSH."""

import json
import os
from pathlib import Path
from aiohttp import web

from . import VERSION
from .policy import validate
from .activity import Reader

STATIC = Path(__file__).parent / "static"


def save(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def application(cfg, config_path, host_identity, process=None, startup_error=None):
    saved = dict(cfg)
    activity_reader = Reader()

    @web.middleware
    async def protect(request, handler):
        if request.remote != os.environ.get("MIRROR_INGRESS_IP", "172.30.32.2"):
            raise web.HTTPForbidden(text="Abre esta app pelo Home Assistant.")
        if request.method not in ("GET", "HEAD") and request.headers.get("X-Steward-UI") != "1":
            raise web.HTTPForbidden()
        try:
            response = await handler(request)
        except ValueError, TypeError, KeyError:
            return web.json_response(
                {"error": "Configuração inválida. Confirma os campos, nomes e chaves públicas."},
                status=400,
            )
        response.headers["Cache-Control"] = "no-store"
        return response

    app = web.Application(middlewares=[protect], client_max_size=65536)

    async def status(request):
        running = process is not None and process.poll() is None
        activity = [activity_reader.get(item["name"]) for item in cfg["sources"]]
        return web.json_response(
            {
                "version": VERSION,
                "listening": running,
                "enabled": cfg["enabled"],
                "restart_required": saved != cfg,
                "error": startup_error,
                "sources": activity,
                "config": saved,
                "timezone": cfg["timezone"],
            }
        )

    async def config(request):
        nonlocal saved
        updated = validate(await request.json())
        save(config_path, updated)
        saved = updated
        return web.json_response(updated)

    async def pairing(request):
        if await request.json() != {}:
            raise ValueError("Esperado objeto vazio.")
        return web.json_response(dict(host_identity(saved["port"]), uuid=saved["uuid"], label=saved["label"]))

    async def disks(request):
        from .storage import inspect

        candidates = []
        try:
            internal = inspect("/media")
            if internal["mount"] == "/media" and internal["filesystem"] == "ext4" and internal["uuid"]:
                candidates.append(dict(internal, mount="/media/mirror", storage_mode="internal"))
        except Exception:
            pass
        for child in sorted(Path("/media").iterdir()):
            if child.is_symlink() or not child.is_dir():
                continue
            try:
                record = inspect(child)
                if record["mount"] == str(child) and record["filesystem"] == "ext4" and record["uuid"]:
                    candidates.append(dict(record, storage_mode="dedicated"))
            except Exception:
                continue
        return web.json_response({"disks": candidates})

    async def index(request):
        return web.Response(
            text=(STATIC / "index.html").read_text(encoding="utf-8"),
            content_type="text/html",
        )

    app.router.add_get("/", index)
    app.router.add_get("/v1/status", status)
    app.router.add_put("/v1/config", config)
    app.router.add_post("/v1/identity", pairing)
    app.router.add_get("/v1/disks", disks)
    app.router.add_static("/static/", STATIC)
    return app
