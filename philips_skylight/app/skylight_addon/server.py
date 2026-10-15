"""Ingress UI and bounded native actions for the managed light integration."""

import asyncio
import hmac
import html
import io
import json
import logging
import re
import secrets
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import aiohttp
from aiohttp import web

from . import DOMAIN, EFFECTS, VERSION, dashboards, esphome_files, slug, unique_id
from .ha import HAError
from .proxies import discover_proxies

LOG = logging.getLogger(__name__)
TRACKING_OPTION = "allow_service_calls"
# The remote's button order. EFFECTS keeps the protocol's order.
REMOTE_ORDER = ("Auto rhythm", "Refresh", "Energize", "Focus", "Relax", "Rest")
CHECK_INTERVAL = 30
# Finding older cards reads every dashboard, so it runs less often.
CARD_CHECK_INTERVAL = 300
SWITCH = "switch.philips_skylight_state_correction"
FIRMWARE_SENSOR = re.compile(r"sensor\.\w*skylight_firmware(?:_\d+)?")

LIGHT_ID = unique_id("light")
SCENE_ID = unique_id("recorded_scene")
CARD_ENTITIES = {
    "light.philips_skylight": LIGHT_ID,
    "select.philips_skylight_recorded_scene": SCENE_ID,
    SWITCH: unique_id("state_correction"),
    **{
        f"button.philips_skylight_{slug(name)}": unique_id(name)
        for name in ("dim_down", "dim_up", *EFFECTS, "record_panel_on", "record_panel_off")
    },
    "button.philips_skylight_set_auto_rhythm_start": unique_id("set_rhythm_start"),
}


def _remaining(until):
    """Whole seconds left in a pairing window, or 0."""
    try:
        end = datetime.fromisoformat(until)
    except (TypeError, ValueError):
        return 0
    return max(0, round((end - datetime.now(UTC)).total_seconds()))


def _version(text):
    return tuple(int(part) for part in text.split("."))


class Panel:
    def __init__(self, ha, installer, root: Path, allowed_ips=None, esphome_dir=None):
        self.ha = ha
        self.installer = installer
        self.root = root
        config = getattr(installer, "ha_config", None)
        self.esphome_dir = esphome_dir or (config / "esphome" if config else None)
        # Read-only checks run in the background and are cached between status polls.
        self.tracking = None
        self.device_builder = None
        self.firmware_files_current = None
        self.outdated_cards = []
        # Dashboards whose card update failed to save. They are not offered again.
        self._cards_unsaved = set()
        # What Home Assistant knows about ESPHome devices, for the setup checks.
        self.esphome_entries = None
        self.proxy_devices = []
        # ESPHome devices that Home Assistant uses as Bluetooth proxies, by node name.
        self.bluetooth_scanners = frozenset()
        self._checked = 0.0
        self._cards_checked = 0.0
        self._check_task = None
        self._auto_setup_tried = False
        self._holds = set()  # Hold commands still on their way to the panel.
        self.allowed_ips = {"172.30.32.2"} if allowed_ips is None else set(allowed_ips)
        self.csrf = secrets.token_urlsafe(32)
        self.lock = asyncio.Lock()
        self.ever_connected = False
        self.first_setup = False
        # Home Assistant paired during this first setup. Pairing again can drop the remote.
        self.setup_paired = False
        # This first setup follows Unpair remotes, so the wall remote is unpaired too.
        self.setup_after_unpair = False
        data = getattr(installer, "data", None)
        self.onboarding_file = data / "onboarding.json" if data is not None else None
        if self.onboarding_file and self.onboarding_file.exists():
            try:
                saved = json.loads(self.onboarding_file.read_text())
                self.first_setup = saved["in_progress"] is True
                # Files from older add-on versions have neither of these keys.
                self.setup_paired = self.first_setup and saved.get("setup_paired") is True
                self.setup_after_unpair = (
                    self.first_setup and saved.get("setup_after_unpair") is True
                )
            except (ValueError, KeyError, TypeError, AttributeError, OSError):
                # Not in setup: the pair action stays locked. Start over reopens setup.
                LOG.warning("Cannot read %s; first setup is not in progress", self.onboarding_file)
                self.first_setup = self.setup_paired = self.setup_after_unpair = False
        ha.on_ready = self.connected
        # Actions that work before the integration has a light entity.
        self.setup_actions = {
            "install": self._install,
            "restart": self._restart,
            "setup": self._setup,
            "prepare_firmware": self._prepare_firmware,
            "allow_tracking": self._allow_tracking,
            "update_firmware": self._update_firmware,
        }
        # Actions that need a loaded, current integration. Each takes (entity, body).
        self.light_actions = {
            "create_dashboard": self._create_dashboard,
            "add_card": self._add_card,
            "sync_state": self._sync_state,
            "sync_mode": self._sync_mode,
            "sync_power": self._sync_power,
            "on": self._power,
            "off": self._power,
            "toggle": self._power,
            "scene": self._scene,
            "dim_up": self._dim,
            "dim_down": self._dim,
            "dim_hold": self._dim_hold,
            "pair": self._pair,
            "unpair_all": self._unpair_all,
            "start_over": self._start_over,
            "skip_sequence": self._skip_sequence,
            "test": self._test,
            "confirm_test": self._confirm_test,
            "finish_setup": self._finish_setup,
            "rhythm_start": self._rhythm_start,
            "update_card": self._update_card,
        }

    async def _save_onboarding(self, in_progress, paired, after_unpair):
        def save():
            if self.onboarding_file:
                self.onboarding_file.parent.mkdir(parents=True, exist_ok=True)
                staging = self.onboarding_file.with_suffix(".tmp")
                staging.write_text(
                    json.dumps(
                        {
                            "in_progress": in_progress,
                            "setup_paired": paired,
                            "setup_after_unpair": after_unpair,
                        }
                    )
                )
                staging.replace(self.onboarding_file)

        await asyncio.to_thread(save)
        self.first_setup = in_progress
        self.setup_paired = paired
        self.setup_after_unpair = after_unpair

    async def set_first_setup(self, in_progress, after_unpair=False):
        # Starting or ending first setup forgets an earlier pairing.
        await self._save_onboarding(in_progress, False, in_progress and after_unpair)

    def connected(self):
        self.check_restarted(reconnected=self.ever_connected)
        self.ever_connected = True

    def check_restarted(self, reconnected=False):
        """Clear the pending restart once Home Assistant runs the installed integration."""
        if not self.installer.pending_restart:
            return
        entity = self.light()
        if entity:
            attributes = self.ha.states.get(entity, {}).get("attributes", {})
            try:
                running = _version(attributes.get("integration_version"))
                done = running >= _version(self.installer.version)
            except (ValueError, AttributeError):
                done = False  # Not loaded yet, or an unreadable version.
        else:
            # With no light to report a version, a new connection is the only sign.
            done = reconnected
        if done:
            self.installer.mark_restarted()

    def entities(self):
        """Map each enabled Skylight unique ID to its current entity ID."""
        return {
            item["unique_id"]: item["entity_id"]
            for item in self.ha.registry
            if item.get("platform") == DOMAIN
            and item.get("unique_id")
            and not item.get("disabled_by")
        }

    def light(self):
        return self.entities().get(LIGHT_ID)

    def button(self, command):
        entity = self.entities().get(unique_id(command))
        if not entity:
            raise HAError("This control entity is disabled or missing in Home Assistant")
        return entity

    def restart_required(self, entity=None):
        """Return whether Core still runs an older integration than the installed one."""
        if self.installer.pending_restart:
            return True
        entity = entity or self.light()
        if not entity:
            return False
        attributes = self.ha.states.get(entity, {}).get("attributes", {})
        running = attributes.get("integration_version")
        try:
            return _version(running) < _version(self.installer.version)
        except (ValueError, AttributeError):
            return True

    def proxies(self):
        return discover_proxies(
            self.ha.states, self.ha.services.get("esphome", {}), self.ha.registry
        )

    def transmit_services(self):
        return sorted(
            service
            for service in self.ha.services.get("esphome", {})
            if service.endswith("_adv_svc_v1")
        )

    def proxy_sensors(self, proxies):
        matched = {item["entity_id"] for item in proxies}
        return [
            {"entity_id": name, "name": item.get("attributes", {}).get("friendly_name", name)}
            for name, item in sorted(self.ha.states.items())
            if name.startswith("sensor.") and ("ble_adv_proxy_name" in name or name in matched)
        ]

    def esphome_nodes(self):
        if not self.esphome_dir:
            return []
        return esphome_files.list_nodes(self.esphome_dir, self.bluetooth_scanners)

    def proxy_entries(self, proxies):
        """ESPHome config entries of the compatible proxies."""
        sensors = {item["entity_id"]: item for item in self.ha.registry}
        return sorted(
            {
                sensors[item["entity_id"]]["config_entry_id"]
                for item in proxies
                if sensors.get(item["entity_id"], {}).get("config_entry_id")
            }
        )

    async def check(self):
        """Refresh the cached remote-tracking setting and the Device Builder link."""
        try:
            entries = self.proxy_entries(self.proxies())
            values = [await self.ha.read_options(entry) for entry in entries]
            self.tracking = (
                all(value.get(TRACKING_OPTION) is True for value in values) if values else None
            )
            self.device_builder = await self.ha.panel_url(
                lambda panel: "esphome" in str((panel.get("config") or {}).get("ingress", ""))
                or "esphome" in str(panel.get("title", "")).lower()
            )
        except (HAError, aiohttp.ClientError, TimeoutError, KeyError, TypeError):
            pass  # Read-only; the next poll tries again.
        try:
            entries = await self.ha.http("GET", "config/config_entries/entry?domain=esphome")
            self.esphome_entries = [
                {"title": item.get("title", ""), "state": item.get("state")}
                for item in entries or []
                if item.get("disabled_by") is None
            ]
            scanners = await self.ha.http("GET", "config/config_entries/entry?domain=bluetooth")
            # Each remote scanner's entry is titled "<node name> (<Bluetooth address>)".
            self.bluetooth_scanners = frozenset(
                str(item.get("title", "")).split(" (")[0] for item in scanners or []
            ) - {""}
            devices = await self.ha.request("config/device_registry/list")
            # A ready-made ESPHome proxy reports the project esphome.bluetooth-proxy.
            self.proxy_devices = sorted(
                {
                    item.get("name_by_user") or item.get("name") or ""
                    for item in devices or []
                    if "bluetooth" in str(item.get("model", "")).lower()
                    and "proxy" in str(item.get("model", "")).lower()
                }
                - {""}
            )
        except (HAError, aiohttp.ClientError, TimeoutError, KeyError, TypeError):
            pass  # Read-only; the next poll tries again.
        if self.esphome_dir:
            try:
                self.firmware_files_current = await asyncio.to_thread(
                    esphome_files.files_current, self.esphome_dir, self.root / "firmware"
                )
            except OSError:
                self.firmware_files_current = None
        if (
            self.light()
            and not self.restart_required()
            and time.monotonic() - self._cards_checked >= CARD_CHECK_INTERVAL
        ):
            self._cards_checked = time.monotonic()
            try:
                found = await dashboards.outdated_cards(
                    self.ha, self.card_entities()[SWITCH], self.card_config()
                )
                self.outdated_cards = [
                    item["title"] for item in found if item["title"] not in self._cards_unsaved
                ]
            except (ValueError, HAError, aiohttp.ClientError, TimeoutError):
                self.outdated_cards = []

    def prerequisites(self, nodes=None):
        """What the first setup step needs: Device Builder, a proxy in it, and a connection."""

        def key(text):
            return re.sub(r"[^a-z0-9]", "", (text or "").lower())

        if nodes is None:
            nodes = self.esphome_nodes()
        builder = bool(self.device_builder) or bool(
            self.esphome_dir and self.esphome_dir.is_dir()
        )
        known = {key(node["node"]) for node in nodes} | {
            key(node.get("friendly_name")) for node in nodes if node.get("friendly_name")
        }
        unadopted = [name for name in self.proxy_devices if key(name) not in known]
        connections = {}
        if self.esphome_entries is not None:
            states = {key(item["title"]): item["state"] for item in self.esphome_entries}
            for node in nodes:
                names = [key(node.get("friendly_name")), key(node["node"])]
                state = next((states[name] for name in names if name and name in states), None)
                if state == "loaded":
                    connections[node["node"]] = "ok"
                elif state:
                    connections[node["node"]] = "offline"
                elif node.get("friendly_name"):
                    # Only claim "not added" when the name Home Assistant uses is known.
                    connections[node["node"]] = "missing"
        return {
            "builder": builder,
            "proxy": "ok" if nodes else "adopt" if unadopted else "none",
            "unadopted": unadopted,
            "connections": connections,
        }

    def firmware_status(self, nodes=None):
        """Whether the proxy firmware is current, needs new files, or needs an install."""
        if nodes is None:
            nodes = self.esphome_nodes()
        nodes = [node for node in nodes if node["uses_package"]]
        if not nodes:
            return None  # Setup adds the firmware, or the proxy is managed elsewhere.
        try:
            bundled = esphome_files.firmware_version(
                (self.root / "firmware" / esphome_files.PACKAGE).read_text()
            )
        except OSError:
            return None
        reported = sorted(
            {
                item.get("state")
                for name, item in self.ha.states.items()
                if FIRMWARE_SENSOR.fullmatch(name)
                and item.get("state") not in (None, "unknown", "unavailable")
            }
        )
        online = any(
            self.ha.states.get(item["entity_id"], {}).get("state") not in (None, "unavailable")
            for item in self.proxies()
        )
        if self.firmware_files_current is False:
            status = "files"
        elif self.firmware_files_current and online and reported != [bundled]:
            # Firmware older than version 1 reports no number at all.
            status = "install"
        else:
            status = "current"
        return {
            "status": status,
            "version": bundled,
            "reported": reported,
            "nodes": [node["node"] for node in nodes],
        }

    def schedule_checks(self):
        if not self.ha.ready or (self._check_task and not self._check_task.done()):
            return
        if time.monotonic() - self._checked >= CHECK_INTERVAL:
            self._checked = time.monotonic()
            self._check_task = asyncio.create_task(self.check())
        elif (
            not self._auto_setup_tried
            and self.installer.installed()
            and not self.restart_required()
            and not self.light()
            and not self.ha.entries
            and len(self.proxies()) == 1
        ):
            # One compatible proxy and no setup yet: save it without asking.
            self._auto_setup_tried = True
            self._check_task = asyncio.create_task(self._auto_setup())

    async def _auto_setup(self):
        try:
            async with self.lock:
                await self._setup({"proxy": self.proxies()[0]["entity_id"]})
        except (ValueError, HAError, aiohttp.ClientError, TimeoutError, IndexError):
            pass  # The page still offers the manual choice.

    def snapshot(self):
        entity = self.light()
        state = self.ha.states.get(entity, {})
        attributes = state.get("attributes", {})
        proxies = self.proxies()
        # Each call reads every ESPHome YAML file, so read them once per snapshot.
        nodes = self.esphome_nodes()
        install_error = getattr(self.installer, "error", None)
        return {
            "version": VERSION,
            "connected": self.ha.ready,
            "error": self.ha.error or install_error,
            "install_error": install_error,
            "installed": self.installer.installed(),
            "restart_required": self.restart_required(entity),
            "configured": bool(entity),
            "first_setup": self.first_setup,
            "setup_paired": self.setup_paired,
            "setup_after_unpair": self.setup_after_unpair,
            "entity_id": entity,
            "name": attributes.get("friendly_name", "Philips Skylight"),
            "state": state.get("state", "unknown") if self.ha.ready else "unavailable",
            "effect": attributes.get("assumed_effect", attributes.get("effect")),
            "last_command": attributes.get("last_command"),
            "power_synchronized": attributes.get("power_synchronized", False),
            "effects": [effect for effect in REMOTE_ORDER if effect in EFFECTS]
            + [effect for effect in EFFECTS if effect not in REMOTE_ORDER],
            "proxies": proxies,
            "transmit_services": self.transmit_services(),
            "proxy_sensors": self.proxy_sensors(proxies),
            "proxy_online": any(
                self.ha.states.get(item["entity_id"], {}).get("state") not in (None, "unavailable")
                for item in proxies
            ),
            "tracking": self.tracking,
            "esphome_nodes": nodes,
            "device_builder": self.device_builder,
            "firmware": self.firmware_status(nodes),
            "prerequisites": self.prerequisites(nodes),
            "outdated_cards": self.outdated_cards,
            "pairing_remaining": _remaining(attributes.get("pairing_until")),
        }

    @web.middleware
    async def access(self, request, handler):
        # The Docker health check runs inside the container and reads only /health.
        local_health = request.path == "/health" and request.remote in ("127.0.0.1", "::1")
        if request.remote not in self.allowed_ips and not local_health:
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
        self.check_restarted()
        self.schedule_checks()
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
        except (TypeError, AttributeError) as err:
            # A field of the wrong type, such as a list where a name belongs.
            LOG.warning("Rejected an action request: %r", err)
            return web.json_response(
                {"ok": False, "error": "The action request has a value of the wrong type"},
                status=400,
            )

    async def perform(self, body):
        action = body.get("action")
        if action in self.setup_actions:
            return await self.setup_actions[action](body)
        if action not in self.light_actions:
            raise ValueError("Unknown action")
        entity = self.light()
        if not entity:
            raise ValueError("Set up the Skylight integration first")
        if self.restart_required(entity):
            raise ValueError("Restart Home Assistant before using the updated integration")
        return await self.light_actions[action](entity, body)

    async def _install(self, body):
        await asyncio.to_thread(self.installer.install)

    async def _restart(self, body):
        if body.get("confirm") is not True:
            raise ValueError("Confirm the Home Assistant restart")
        await self.ha.call("homeassistant", "restart")

    async def _setup(self, body):
        if self.restart_required():
            raise ValueError("Restart Home Assistant to load the installed integration first")
        proxies = self.proxies()
        service = body.get("transmit_service")
        proxy = body.get("proxy_entity")
        if "proxy" in body:
            candidate = next(
                (item for item in proxies if item["entity_id"] == body["proxy"]), None
            )
            if candidate is None:
                raise ValueError("Choose an available Skylight proxy")
            proxy, service = candidate["entity_id"], candidate["transmit_service"]
        if not isinstance(service, str) or not isinstance(proxy, str):
            raise ValueError("Choose a transmitter and its proxy sensor")
        if service not in self.transmit_services():
            raise ValueError("Choose an available advertising action")
        if proxy not in {item["entity_id"] for item in self.proxy_sensors(proxies)}:
            raise ValueError("Choose a BLE Adv Proxy Name sensor")
        name = body.get("name", "Philips Skylight")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("Enter a light name of 1–80 characters")
        if not self.ha.entries and not self.light():
            await self.set_first_setup(True)
        await self.ha.configure(name.strip(), service, proxy)

    async def _create_dashboard(self, entity, body):
        self._cards_checked = 0
        return await dashboards.create_dashboard(self.ha, self.card_config())

    async def _update_card(self, entity, body):
        result = await dashboards.update_cards(
            self.ha, self.card_entities()[SWITCH], self.card_config()
        )
        self._cards_unsaved.update(result["failed"])
        self.outdated_cards = []
        self._cards_checked = 0
        if result["failed"]:
            done = f"Card updated on {', '.join(result['updated'])}. " if result["updated"] else ""
            raise HAError(
                f"{done}Home Assistant did not save {', '.join(result['failed'])}. "
                "Replace the card there by hand."
            )
        return result

    async def _add_card(self, entity, body):
        self._cards_checked = 0
        return await dashboards.add_card(
            self.ha,
            body.get("url_path"),
            body.get("view_index"),
            body.get("revision"),
            self.card_config(),
        )

    async def _sync_state(self, entity, body):
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

    async def _sync_mode(self, entity, body):
        effect = body.get("effect")
        if effect not in (*EFFECTS, "Unknown"):
            raise ValueError("Choose a mode or Unknown")
        entities = self.card_entities()
        await self.ha.call(
            "select",
            "select_option",
            entities["select.philips_skylight_recorded_scene"],
            option=effect,
        )

    async def _sync_power(self, entity, body):
        if type(body.get("is_on")) is not bool:
            raise ValueError("Specify whether the panel is currently on")
        await self.ha.call(DOMAIN, "set_assumed_power", entity, is_on=body["is_on"])
        await self.set_first_setup(False)

    async def _power(self, entity, body):
        action = body["action"]
        await self.ha.call("light", "toggle" if action == "toggle" else f"turn_{action}", entity)

    async def _scene(self, entity, body):
        effect = body.get("effect")
        if effect not in EFFECTS:
            raise ValueError("Unknown scene")
        await self.ha.call("button", "press", self.button(effect))

    async def _dim(self, entity, body):
        await self.ha.call("button", "press", self.button(body["action"]))

    async def _unpair_all(self, entity, body):
        if body.get("confirm") is not True:
            raise ValueError("Tick the box first")
        await self.ha.call(DOMAIN, "unpair_all_remotes", entity, confirm=True)

    async def _start_over(self, entity, body):
        # Unpair remotes made the panel forget every remote. The setup checklist now
        # pairs Home Assistant first, then the user pairs the wall remote again.
        await self.set_first_setup(True, after_unpair=True)

    async def _dim_hold(self, entity, body):
        direction = body.get("direction")
        if direction not in ("down", "up"):
            raise ValueError("Choose a dim direction")
        # One hold command. The page asks again every 0.6 seconds while pressed,
        # so answer at once: the integration waits 0.6 seconds after each command.
        if len(self._holds) >= 2:
            return  # A slow link must not queue steps that keep dimming after release.
        task = asyncio.create_task(
            self.ha.call(DOMAIN, "dim", entity, direction=direction, hold=0.6)
        )
        self._holds.add(task)
        task.add_done_callback(self._hold_done)

    def _hold_done(self, task):
        self._holds.discard(task)
        if not task.cancelled() and task.exception():
            LOG.warning("A hold command failed: %s", task.exception())

    async def _pair(self, entity, body):
        if body.get("confirm") is not True:
            raise ValueError("Confirm that the panel just came back on")
        if not self.first_setup or self.setup_paired:
            # Pairing Home Assistant again can make the panel drop the wall remote.
            raise ValueError(
                "Home Assistant is already paired. Pairing again can drop the wall remote. "
                "To pair again, use Settings and fixes → Unpair remotes."
            )
        # Returns at once; the integration sends the request for 10 seconds.
        await self.ha.call(DOMAIN, "pair_transmitter", entity, confirm=True)
        # A page reload now skips to the test step instead of offering Pair again.
        await self._save_onboarding(True, True, self.setup_after_unpair)

    async def _prepare_firmware(self, body):
        if not self.esphome_dir:
            raise ValueError("The ESPHome folder is not available to this add-on")
        firmware = self.root / "firmware"
        result = await asyncio.to_thread(
            esphome_files.install_package,
            self.esphome_dir,
            firmware,
            body.get("file"),
            self.bluetooth_scanners,  # The same proxies the page lists.
        )
        self._checked = 0  # Look for the Device Builder link again.
        return result

    async def _update_firmware(self, body):
        if not self.esphome_dir:
            raise ValueError("The ESPHome folder is not available to this add-on")
        result = await asyncio.to_thread(
            esphome_files.update_files,
            self.esphome_dir,
            self.root / "firmware",
            self.bluetooth_scanners,
        )
        self.firmware_files_current = None
        self._checked = 0  # Compare the files again on the next poll.
        return result

    async def _allow_tracking(self, body):
        entries = self.proxy_entries(self.proxies())
        if not entries:
            raise ValueError("No compatible Bluetooth proxy is online")
        for entry in entries:
            await self.ha.set_options(entry, {TRACKING_OPTION: True})
        self.tracking = True

    async def _test(self, entity, body):
        # A power change is easy to see; a mode change often is not.
        await self.ha.call("light", "toggle", entity)

    async def _confirm_test(self, entity, body):
        result = body.get("result")
        if result not in ("on", "off", "none"):
            raise ValueError("Say what the panel did")
        if result != "none":
            # The answer also tells Home Assistant the real power state.
            await self.ha.call(DOMAIN, "set_assumed_power", entity, is_on=result == "on")
        elif self.first_setup:
            # The pairing did not take, so the checklist offers Pair again.
            await self._save_onboarding(True, False, self.setup_after_unpair)

    async def _finish_setup(self, entity, body):
        effect = body.get("effect")
        if effect is not None:
            if effect not in EFFECTS:
                raise ValueError("Unknown mode")
            # A mode command leaves the panel on in that mode, so both become known.
            await self.ha.call("button", "press", self.button(effect))
        await self.set_first_setup(False)

    async def _rhythm_start(self, entity, body):
        await self.ha.call("button", "press", self.button("set_rhythm_start"))

    async def _skip_sequence(self, entity, body):
        if body.get("confirm") is not True:
            raise ValueError("Confirm that the panel ignores commands after a restore or rebuild")
        await self.ha.call(DOMAIN, "skip_sequence", entity, confirm=True)

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
        if not self.ha.ready or self.restart_required():
            raise ValueError("Wait for Home Assistant to load the updated integration")
        entities = self.entities()
        replacements = {}
        for default, unique in CARD_ENTITIES.items():
            entity = entities.get(unique)
            if (
                not entity
                or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity)
                or entity.split(".")[0] != default.split(".")[0]
            ):
                raise ValueError(f"Enable the Skylight control entity: {unique}")
            replacements[default] = entity
        return replacements

    def card_config(self):
        card = json.loads((self.root / "static/skylight-cards.json").read_text())["card"]
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
            replacements = self.card_entities()
        except ValueError as err:
            raise web.HTTPBadRequest(text=str(err)) from err
        filename = "skylight-card.yaml"
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
