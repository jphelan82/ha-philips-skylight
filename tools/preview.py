"""Click through the add-on page with a fake backend. Sends nothing to Home Assistant.

Run: python tools/preview.py [port] [stage]. Each action moves the fake setup one
stage on. The stage starts the page at another point, for screenshots: "missing"
(nothing set up yet), "install", "pair" or "ready".
"""

import asyncio
import re
import sys
from pathlib import Path

from aiohttp import web

STATIC = Path(__file__).resolve().parents[1] / "philips_skylight/app/static"
INIT = STATIC.parent / "skylight_addon/__init__.py"
VERSION = re.search(r'VERSION = "([^"]+)"', INIT.read_text())[1]
PROXY = {"entity_id": "sensor.p", "name": "Bluetooth Proxy", "node": "proxy-1",
         "transmit_service": "proxy_1_adv_svc_v1"}
state = {
    "connected": True, "installed": True, "restart_required": False, "configured": False,
    "first_setup": False, "setup_paired": False, "setup_after_unpair": False,
    "state": "unknown", "effect": None, "name": "Philips Skylight",
    "version": VERSION, "entity_id": None,
    "effects": ["Auto rhythm", "Refresh", "Energize", "Focus", "Relax", "Rest"],
    "proxies": [], "transmit_services": [], "proxy_sensors": [], "proxy_online": False,
    "tracking": None, "esphome_nodes": [{"file": "proxy-1.yaml", "node": "proxy-1",
                                          "has_skylight": False}],
    "device_builder": "#", "pairing_remaining": 0,
    "prerequisites": {"builder": True, "proxy": "ok", "unadopted": [],
                      "connections": {"proxy-1": "ok"}},
}


async def countdown(seconds):
    state["pairing_remaining"] = seconds
    while state["pairing_remaining"] > 0:
        await asyncio.sleep(1)
        state["pairing_remaining"] = max(0, state["pairing_remaining"] - 1)


async def later(seconds, **changes):
    await asyncio.sleep(seconds)
    state.update(changes)


async def index(request):
    text = (STATIC / "index.html").read_text().replace("__BASE__", "/").replace("__CSRF__", "x")
    return web.Response(text=text, content_type="text/html")


async def status(request):
    return web.json_response(state)


async def action(request):
    body = await request.json()
    kind = body.get("action")
    if kind == "prepare_firmware":
        state["esphome_nodes"][0]["has_skylight"] = True
        # The user installs it in Device Builder; the proxy comes back, then connects.
        asyncio.create_task(later(6, proxies=[PROXY], proxy_online=True))
        asyncio.create_task(later(9, configured=True, first_setup=True, entity_id="light.x",
                                  tracking=False))
        return web.json_response({"ok": True, "changed": True})
    if kind == "allow_tracking":
        state["tracking"] = True
    elif kind == "pair":
        state["last_command"] = "pair"
        if state["first_setup"]:
            state["setup_paired"] = True
        asyncio.create_task(countdown(10))
    elif kind == "start_over":
        # The panel forgot every remote: the setup checklist pairs Home Assistant next.
        state.update(first_setup=True, setup_paired=False, setup_after_unpair=True)
    elif kind == "unpair_all":
        state["last_command"] = "unpair all"
        asyncio.create_task(countdown(10))
    elif kind == "scene":
        state.update(state="on", effect=body["effect"])
    elif kind == "confirm_test" and body.get("result") in ("on", "off"):
        state["state"] = body["result"]
    elif kind == "confirm_test":
        state["setup_paired"] = False  # The pairing did not take, so Pair opens again.
    elif kind == "finish_setup":
        state.update(first_setup=False, setup_paired=False, setup_after_unpair=False)
        if body.get("effect"):
            state.update(state="on", effect=body["effect"])
    elif kind in ("toggle", "test"):
        state["state"] = {"on": "off", "off": "on"}.get(state["state"], "unknown")
    elif kind == "sync_power":
        state["state"] = "on" if body.get("is_on") else "off"
    return web.json_response({"ok": True})


STAGES = {
    "pair": {
        "proxies": [PROXY], "proxy_online": True, "configured": True, "first_setup": True,
        "entity_id": "light.x", "tracking": True,
        "esphome_nodes": [{"file": "proxy-1.yaml", "node": "proxy-1", "has_skylight": True,
                           "uses_package": True, "api_key": True}],
    },
}
STAGES["missing"] = {
    "esphome_nodes": [], "device_builder": None,
    "prerequisites": {"builder": False, "proxy": "none", "unadopted": [], "connections": {}},
}
STAGES["install"] = {
    "esphome_nodes": [{"file": "proxy-1.yaml", "node": "proxy-1", "friendly_name": "Bluetooth Proxy",
                       "has_skylight": True, "uses_package": True, "api_key": True}],
}
STAGES["ready"] = {**STAGES["pair"], "first_setup": False, "state": "on", "effect": "Relax"}
if len(sys.argv) > 2:
    state.update(STAGES[sys.argv[2]])

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/api/status", status)
app.router.add_post("/api/action", action)
app.router.add_static("/static/", STATIC)
web.run_app(app, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
