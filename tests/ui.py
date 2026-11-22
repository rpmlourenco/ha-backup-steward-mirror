"""Receiver UI acceptance; fake endpoints, public fixture keys, no real HA."""

import base64
import json
import os
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
KEY = "ssh-ed25519 " + base64.b64encode(b"\0\0\0\x0bssh-ed25519\0\0\0\x20" + bytes(32)).decode()
UUID = "11111111-1111-4111-8111-111111111111"


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/static/"):
            self.path = self.path.removeprefix("/static")
        return super().do_GET()


cfg = dict(
    enabled=False,
    label="Lisboa",
    mount="/media/mirror",
    uuid=UUID,
    port=2222,
    min_free_gib=20,
    sources=[],
    timezone="Europe/Madrid",
)
activities = []
offline = False
saved = False


def route(r):
    global cfg, saved
    if offline:
        return r.abort()
    path = r.request.url.split("/v1/")[1]
    if path == "status":
        return r.fulfill(
            json=dict(
                version="0.1.0",
                listening=False,
                enabled=False,
                restart_required=saved,
                error=None,
                sources=activities,
                timezone="Europe/Madrid",
                config=cfg,
            )
        )
    if path == "disks":
        return r.fulfill(json={"disks": [{"mount": "/media/mirror", "uuid": UUID}]})
    if path == "identity":
        return r.fulfill(json=dict(protocol="steward-mirror-v1", host_key=KEY, port=2222, uuid=UUID))
    if path == "config":
        cfg = r.request.post_data_json
        saved = True
        return r.fulfill(json=cfg)
    return r.fulfill(status=404, json={})


server = ThreadingHTTPServer(
    ("127.0.0.1", 0), partial(Handler, directory=str(ROOT / "mirror/receiver/static"))
)
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            **(
                {"executable_path": os.environ["STEWARD_TEST_BROWSER"]}
                if os.environ.get("STEWARD_TEST_BROWSER")
                else {}
            ),
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1080})
        page.add_init_script("window.testPollers=[];window.setInterval=fn=>window.testPollers.push(fn)")
        page.route("**/v1/**", route)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server.server_port}")
        page.wait_for_function("!document.getElementById('save').disabled")
        page.locator("#pairing").fill(
            json.dumps(
                dict(
                    protocol="steward-mirror-v1",
                    sources=[
                        dict(name="immich", public_key=KEY),
                        dict(name="filebrowser", public_key=KEY),
                    ],
                )
            )
        )
        page.locator("#import").click()
        assert page.locator(".mirror-source").count() == 2
        page.locator("#save").click()
        page.wait_for_function("!document.getElementById('notice').hidden")
        assert len(cfg["sources"]) == 2
        page.locator("#identity").click()
        page.locator("#identity-value").wait_for(state="visible")
        assert json.loads(page.locator("#identity-value").input_value())["host_key"] == KEY
        previews = ROOT / "test-artifacts/previews"
        previews.mkdir(parents=True, exist_ok=True)
        activities.append(
            {
                "name": "immich",
                "status": "receiving",
                "operation": "receiving",
                "elapsed_seconds": 65,
                "started_at": "2026-11-22T12:00:00+00:00",
                "time": "2026-11-22T12:01:05+00:00",
                "events": [
                    {
                        "kind": "receiving_started",
                        "message": "Receção iniciada",
                        "seq": 1,
                        "time": "2026-11-22T12:00:00+00:00",
                    }
                ],
            }
        )
        page.evaluate("window.testPollers.forEach(fn=>fn())")
        page.wait_for_function("document.getElementById('activity').textContent.includes('A receber')")
        assert "1m 5s" in page.locator("#activity").inner_text()
        assert page.locator("#activity progress").get_attribute("value") is None
        assert "Receção iniciada" in page.locator("#recent-events").inner_text()
        assert page.locator("#recent-events time").inner_text()
        page.screenshot(path=str(previews / "receiver-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(previews / "receiver-mobile.png"), full_page=True)
        offline = True
        page.evaluate("window.testPollers.forEach(fn=>fn())")
        page.wait_for_function("document.getElementById('save').disabled")
        for name in ("import", "identity", "copy", "disks"):
            assert page.locator("#" + name).is_disabled()
        assert not errors, errors
        browser.close()
        print(
            "Receiver UI passed: pairing import, identity export, persisted settings, restart notice, offline locks, desktop/mobile layout."
        )
finally:
    server.shutdown()
