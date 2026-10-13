"""Ingress UI and bounded native actions for the managed light integration."""

import asyncio
import hmac
import html
import io
import json
import re
import secrets
import zipfile
from pathlib import Path

import aiohttp
from aiohttp import web

from . import DOMAIN, VERSION, dashboards
from .ha import HAError
from .proxies import discover_proxies

EFFECTS = ("Refresh", "Energize", "Focus", "Relax", "Rest", "Auto rhythm")
CARD_ENTITIES = {
    "light.philips_skylight": "factory_mesh_7ffe_light",
    "select.philips_skylight_recorded_scene": "factory_mesh_7ffe_recorded_scene",
    "switch.philips_skylight_state_correction": "factory_mesh_7ffe_state_correction",
    **{
        f"button.philips_skylight_{slug}": f"factory_mesh_7ffe_{slug}"
        for slug in (
            "dim_down",
            "dim_up",
            *(effect.lower().replace(" ", "_") for effect in EFFECTS),
            "record_panel_on",
            "record_panel_off",
        )
    },
}


class Panel:
    def __init__(self, ha, installer, root: Path, allowed_ips=None):
        self.ha = ha
        self.installer = installer
        self.root = root
        self.allowed_ips = {"172.30.32.2"} if allowed_ips is None else set(allowed_ips)
        self.csrf = secrets.token_urlsafe(32)
        self.lock = asyncio.Lock()
        self.ever_connected = False
        self.first_setup = False
        data = getattr(installer, "data", None)
        self.onboarding_file = data / "onboarding.json" if data is not None else None
        if self.onboarding_file and self.onboarding_file.exists():
            try:
                self.first_setup = (
                    json.loads(self.onboarding_file.read_text())["in_progress"] is True
                )
            except (ValueError, KeyError, TypeError, OSError):
                self.first_setup = True  # Show help; never trigger a physical action.
        ha.on_ready = self.connected

    async def set_first_setup(self, in_progress):
        def save():
            if self.onboarding_file:
                self.onboarding_file.parent.mkdir(parents=True, exist_ok=True)
                staging = self.onboarding_file.with_suffix(".tmp")
                staging.write_text(json.dumps({"in_progress": in_progress}))
                staging.replace(self.onboarding_file)

        await asyncio.to_thread(save)
        self.first_setup = in_progress

    def connected(self):
        if self.ever_connected and self.installer.pending_restart:
            self.installer.mark_restarted()
        self.ever_connected = True

    def light(self):
        return next(
            (
                item["entity_id"]
                for item in self.ha.registry
                if item.get("platform") == DOMAIN
                and item.get("unique_id") == "factory_mesh_7ffe_light"
                and not item.get("disabled_by")
            ),
            None,
        )

    def button(self, command):
        unique_id = f"factory_mesh_7ffe_{command.lower().replace(' ', '_')}"
        entity = next(
            (
                item["entity_id"]
                for item in self.ha.registry
                if item.get("platform") == DOMAIN
                and item.get("unique_id") == unique_id
                and not item.get("disabled_by")
            ),
            None,
        )
        if not entity:
            raise HAError("This control entity is disabled or missing in Home Assistant")
        return entity

    def snapshot(self):
        entity = self.light()
        state = self.ha.states.get(entity, {})
        attributes = state.get("attributes", {})
        running = attributes.get("integration_version")
        try:
            stale = bool(entity) and (
                not running
                or tuple(int(n) for n in running.split("."))
                < tuple(int(n) for n in self.installer.version.split("."))
            )
        except (ValueError, AttributeError):
            stale = bool(entity)
        return {
            "version": VERSION,
            "connected": self.ha.ready,
            "error": self.ha.error,
            "installed": self.installer.installed(),
            "restart_required": self.installer.pending_restart or stale,
            "configured": bool(entity),
            "first_setup": self.first_setup,
            "entity_id": entity,
            "name": attributes.get("friendly_name", "Philips Skylight"),
            "state": state.get("state", "unknown") if self.ha.ready else "unavailable",
            "effect": attributes.get("assumed_effect", attributes.get("effect")),
            "last_command": attributes.get("last_command"),
            "power_synchronized": attributes.get("power_synchronized", False),
            "effects": list(EFFECTS),
            "proxies": discover_proxies(
                self.ha.states, self.ha.services.get("esphome", {}), self.ha.registry
            ),
            "transmit_services": sorted(
                service
                for service in self.ha.services.get("esphome", {})
                if service.endswith("_adv_svc_v1")
            ),
            "proxy_sensors": [
                {"entity_id": name, "name": item.get("attributes", {}).get("friendly_name", name)}
                for name, item in sorted(self.ha.states.items())
                if name.startswith("sensor.")
                and (
                    "ble_adv_proxy_name" in name
                    or name
                    in {
                        item["entity_id"]
                        for item in discover_proxies(
                            self.ha.states, self.ha.services.get("esphome", {}), self.ha.registry
                        )
                    }
                )
            ],
        }

    @web.middleware
    async def access(self, request, handler):
        if request.remote not in self.allowed_ips:
            raise web.HTTPForbidden(text="Use Home Assistant ingress")
        if request.method == "POST":
            if request.content_type != "application/json" or not hmac.compare_digest(
                request.headers.get("X-Skylight-CSRF", ""), self.csrf
            ):
                raise web.HTTPForbidden(text="Invalid action session")
        response = await handler(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        )
        return response

    async def index(self, request):
        base = request.headers.get("X-Ingress-Path", "")
        if base and (not base.startswith("/") or base.startswith("//")):
            raise web.HTTPBadRequest()
        content = (self.root / "static/index.html").read_text()
        content = content.replace("__BASE__", html.escape(base.rstrip("/") + "/", quote=True))
        content = content.replace("__CSRF__", self.csrf)
        return web.Response(text=content, content_type="text/html")

    async def status(self, request):
        return web.json_response(self.snapshot())

    async def health(self, request):
        # Process health, not HA readiness: do not restart the app during a Core reboot.
        return web.json_response({"ok": True, "connected": self.ha.ready})

    async def action(self, request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("Action must be a JSON object")
            async with self.lock:
                result = await self.perform(body)
            return web.json_response({"ok": True, **(result or {})})
        except (ValueError, HAError, aiohttp.ClientError, TimeoutError, OSError) as err:
            return web.json_response({"ok": False, "error": str(err)[:400]}, status=400)

    async def perform(self, body):
        action = body.get("action")
        if action == "install":
            await asyncio.to_thread(self.installer.install)
            return
        if action == "restart":
            if body.get("confirm") is not True:
                raise ValueError("Confirm the Home Assistant restart")
            await self.ha.call("homeassistant", "restart")
            return
        if action == "setup":
            if self.snapshot()["restart_required"]:
                raise ValueError("Restart Home Assistant to load the installed integration first")
            service = body.get("transmit_service")
            proxy = body.get("proxy_entity")
            if "proxy" in body:
                candidate = next(
                    (
                        item
                        for item in self.snapshot()["proxies"]
                        if item["entity_id"] == body["proxy"]
                    ),
                    None,
                )
                if candidate is None:
                    raise ValueError("Choose an available Skylight proxy")
                proxy, service = candidate["entity_id"], candidate["transmit_service"]
            if not isinstance(service, str) or not isinstance(proxy, str):
                raise ValueError("Choose a transmitter and its proxy sensor")
            if service not in self.snapshot()["transmit_services"]:
                raise ValueError("Choose an available advertising action")
            if proxy not in {s["entity_id"] for s in self.snapshot()["proxy_sensors"]}:
                raise ValueError("Choose a BLE Adv Proxy Name sensor")
            name = body.get("name", "Philips Skylight")
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
                raise ValueError("Enter a light name of 1–80 characters")
            if not self.ha.entries and not self.light():
                await self.set_first_setup(True)
            await self.ha.configure(name.strip(), service, proxy)
            return
        entity = self.light()
        if not entity:
            raise ValueError("Set up the Skylight integration first")
        if self.snapshot()["restart_required"]:
            raise ValueError("Restart Home Assistant before using the updated integration")
        if action == "create_dashboard":
            return await dashboards.create_dashboard(self.ha, self.card_config(body.get("style")))
        if action == "add_card":
            return await dashboards.add_card(
                self.ha,
                body.get("url_path"),
                body.get("view_index"),
                body.get("revision"),
                self.card_config(body.get("style")),
            )
        if action == "sync_state":
            power, effect = body.get("power"), body.get("effect")
            if power not in ("on", "off") or effect not in (*EFFECTS, "Unknown"):
                raise ValueError("Record the power you can see and a mode (or Unknown)")
            # Resolve every entity before making either local-only change.
            entities = self.card_entities()
            await self.ha.call(
                "button", "press", entities[f"button.philips_skylight_record_panel_{power}"]
            )
            await self.ha.call(
                "select",
                "select_option",
                entities["select.philips_skylight_recorded_scene"],
                option=effect,
            )
            await self.set_first_setup(False)
        elif action in ("on", "off", "toggle"):
            service = "toggle" if action == "toggle" else f"turn_{action}"
            await self.ha.call("light", service, entity)
        elif action == "scene":
            effect = body.get("effect")
            if effect not in EFFECTS:
                raise ValueError("Unknown scene")
            await self.ha.call("button", "press", self.button(effect))
        elif action in ("dim_up", "dim_down"):
            await self.ha.call("button", "press", self.button(action))
        elif action == "sync_mode":
            effect = body.get("effect")
            if effect not in (*EFFECTS, "Unknown"):
                raise ValueError("Choose a mode or Unknown")
            entities = self.card_entities()
            await self.ha.call(
                "select", "select_option", entities["select.philips_skylight_recorded_scene"],
                option=effect,
            )
        elif action == "sync_power":
            if type(body.get("is_on")) is not bool:
                raise ValueError("Specify whether the panel is currently on")
            await self.ha.call(DOMAIN, "set_assumed_power", entity, is_on=body["is_on"])
            await self.set_first_setup(False)
        elif action == "pair":
            if body.get("confirm") is not True:
                raise ValueError("Confirm the possible change to the original remote's pairing")
            await self.ha.call(DOMAIN, "pair_transmitter", entity, confirm=True)
        else:
            raise ValueError("Unknown action")

    async def firmware(self, request):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in (self.root / "firmware").rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(self.root / "firmware"))
        return web.Response(
            body=data.getvalue(),
            content_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="skylight-proxy-firmware.zip"'},
        )

    def card_entities(self):
        if not self.ha.ready or self.snapshot()["restart_required"]:
            raise ValueError("Wait for Home Assistant to load the updated integration")
        replacements = {}
        for default, unique_id in CARD_ENTITIES.items():
            entity = next(
                (
                    item["entity_id"]
                    for item in self.ha.registry
                    if item.get("platform") == DOMAIN
                    and item.get("unique_id") == unique_id
                    and not item.get("disabled_by")
                ),
                None,
            )
            if (
                not entity
                or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity)
                or entity.split(".")[0] != default.split(".")[0]
            ):
                raise ValueError(f"Enable the Skylight control entity: {unique_id}")
            replacements[default] = entity
        return replacements

    def card_style(self, style):
        style = "compact" if style is None else style
        if style not in ("compact", "full"):
            raise ValueError("Choose a compact or full card")
        return style

    def card_config(self, style=None):
        card = json.loads((self.root / "static/skylight-cards.json").read_text())[
            self.card_style(style)
        ]
        replacements = self.card_entities()

        def replace(value):
            if isinstance(value, dict):
                return {key: replace(child) for key, child in value.items()}
            if isinstance(value, list):
                return [replace(child) for child in value]
            return replacements.get(value, value) if isinstance(value, str) else value

        return replace(card)

    async def dashboard_card(self, request):
        """Export standard cards using registry IDs, including renamed entities."""
        try:
            style = self.card_style(request.query.get("style"))
            replacements = self.card_entities()
        except ValueError as err:
            raise web.HTTPBadRequest(text=str(err)) from err
        filename = "skylight-card-compact.yaml" if style == "compact" else "skylight-card.yaml"
        card = (self.root / "static" / filename).read_text()
        # Replace once so a renamed entity that matches another default is safe.
        pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, replacements)) + r")\b")
        card = pattern.sub(lambda match: replacements[match[0]], card)
        return web.Response(
            text=card,
            content_type="application/yaml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async def dashboard_choices(self, request):
        try:
            path = request.query.get("url_path")
            if path is None:
                result = {"dashboards": await dashboards.list_dashboards(self.ha)}
            else:
                config = await dashboards.load_dashboard(self.ha, path)
                result = {
                    "views": dashboards.editable_views(config),
                    "revision": dashboards.revision(config),
                }
            return web.json_response(result)
        except (ValueError, HAError, aiohttp.ClientError, TimeoutError) as err:
            return web.json_response({"error": str(err)[:400]}, status=400)

    def app(self):
        app = web.Application(middlewares=[self.access], client_max_size=8192)
        app.router.add_get("/", self.index)
        app.router.add_get("/api/status", self.status)
        app.router.add_post("/api/action", self.action)
        app.router.add_get("/api/firmware", self.firmware)
        app.router.add_get("/api/dashboard-card", self.dashboard_card)
        app.router.add_get("/api/dashboards", self.dashboard_choices)
        app.router.add_get("/health", self.health)
        app.router.add_static("/static/", self.root / "static")
        return app
