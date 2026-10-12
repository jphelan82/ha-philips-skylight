"""Authenticated native HA connection; never retry a control request."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress

import aiohttp

from . import DOMAIN

LOG = logging.getLogger(__name__)


class HAError(Exception):
    """A native HA request failed or its result is uncertain."""


class HAClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_base="http://supervisor/core/api",
        websocket_url="ws://supervisor/core/websocket",
    ):
        self.session = session
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.websocket_url = websocket_url
        self.ready = False
        self.states = {}
        self.services = {}
        self.registry = []
        self.entries = []
        self.error = "Connecting to Home Assistant"
        self.on_ready: Callable[[], None] = lambda: None
        self._ws = None
        self._id = 0
        self._pending = {}
        self._task = None
        self._refresh_task = None

    async def start(self):
        self._task = asyncio.create_task(self._run())

    async def close(self):
        if self._refresh_task:
            self._refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._refresh_task
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def request(self, kind: str, **data):
        if self._ws is None or self._ws.closed:
            raise HAError("Home Assistant is disconnected; no command was retried")
        self._id += 1
        request_id = self._id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._ws.send_json({"id": request_id, "type": kind, **data})
            async with asyncio.timeout(20):
                return await future
        except TimeoutError as err:
            raise HAError("Request timed out. Its result is uncertain; it was not retried") from err
        finally:
            self._pending.pop(request_id, None)

    async def http(self, method: str, path: str, body=None):
        async with self.session.request(
            method,
            f"{self.api_base}/{path}",
            headers={"Authorization": f"Bearer {self.token}"},
            json=body,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            if response.status >= 400:
                raise HAError(f"Home Assistant returned HTTP {response.status}")
            return await response.json()

    async def refresh(self):
        self.states = {s["entity_id"]: s for s in await self.request("get_states")}
        self.services = await self.request("get_services")
        self.registry = await self.request("config/entity_registry/list")
        self.entries = await self.http("GET", f"config/config_entries/entry?domain={DOMAIN}")

    async def _refresh_later(self):
        await asyncio.sleep(0.5)
        try:
            if self.ready:
                await self.refresh()
        except (HAError, aiohttp.ClientError, TimeoutError):
            # These are read requests. Connection setup will refresh again.
            pass

    async def call(self, domain: str, service: str, entity: str | None = None, **data):
        if not self.ready:
            raise HAError("Wait for Home Assistant to reconnect")
        body = {"domain": domain, "service": service, "service_data": data}
        if entity:
            body["target"] = {"entity_id": entity}
        return await self.request("call_service", **body)

    async def configure(self, name: str, service: str, proxy: str):
        if not self.ready:
            raise HAError("Wait for Home Assistant to reconnect")
        body = {"handler": DOMAIN}
        if self.entries:
            body["entry_id"] = self.entries[0]["entry_id"]
        flow = await self.http("POST", "config/config_entries/flow", body)
        if flow.get("type") != "form":
            raise HAError(f"Cannot start setup: {flow.get('reason', flow.get('type'))}")
        result = await self.http(
            "POST",
            f"config/config_entries/flow/{flow['flow_id']}",
            {"name": name, "transmit_service": service, "proxy_entity": proxy},
        )
        if result.get("type") == "form":
            raise HAError(f"Setup needs correction: {result.get('errors', {})}")
        if result.get("type") not in ("create_entry", "abort") or (
            result.get("type") == "abort" and result.get("reason") != "reconfigure_successful"
        ):
            raise HAError(f"Setup failed: {result.get('reason', result.get('type'))}")
        await self.refresh()

    async def _read(self, ws):
        async for frame in ws:
            if frame.type != aiohttp.WSMsgType.TEXT:
                continue
            message = frame.json()
            if message.get("type") == "result":
                future = self._pending.get(message["id"])
                if future and not future.done():
                    if message.get("success"):
                        future.set_result(message.get("result"))
                    else:
                        error = message.get("error", {})
                        future.set_exception(HAError(str(error.get("message", "Request failed"))))
            elif message.get("type") == "event":
                event = message["event"]
                data = event.get("data", {})
                if event.get("event_type") == "state_changed":
                    if data.get("new_state"):
                        self.states[data["entity_id"]] = data["new_state"]
                    else:
                        self.states.pop(data.get("entity_id"), None)
                elif event.get("event_type") in (
                    "service_registered",
                    "service_removed",
                    "entity_registry_updated",
                ) and (self._refresh_task is None or self._refresh_task.done()):
                    self._refresh_task = asyncio.create_task(self._refresh_later())
        raise HAError("Home Assistant connection closed")

    async def _run(self):
        delay = 1
        while True:
            reader = None
            try:
                async with self.session.ws_connect(
                    self.websocket_url,
                    heartbeat=20,
                    timeout=aiohttp.ClientWSTimeout(ws_close=5),
                ) as ws:
                    challenge = await ws.receive_json(timeout=10)
                    if challenge.get("type") != "auth_required":
                        raise HAError("Unexpected Home Assistant authentication response")
                    await ws.send_json({"type": "auth", "access_token": self.token})
                    result = await ws.receive_json(timeout=10)
                    if result.get("type") != "auth_ok":
                        raise HAError("Home Assistant rejected the add-on credentials")
                    self._ws = ws
                    reader = asyncio.create_task(self._read(ws))
                    for event_type in (
                        "state_changed",
                        "service_registered",
                        "service_removed",
                        "entity_registry_updated",
                    ):
                        await self.request("subscribe_events", event_type=event_type)
                    await self.refresh()
                    self.ready = True
                    self.error = None
                    self.on_ready()
                    LOG.info("Connected to Home Assistant")
                    delay = 1
                    await reader
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, HAError, TimeoutError, ValueError, OSError) as err:
                self.error = str(err)[:300]
                LOG.warning(
                    "HA connection unavailable (%s); reconnecting in %ss", type(err).__name__, delay
                )
            finally:
                self.ready = False
                self._ws = None
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(HAError("Connection lost; request was not retried"))
                if reader and not reader.done():
                    reader.cancel()
                if reader:
                    with suppress(asyncio.CancelledError, Exception):
                        await reader
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
