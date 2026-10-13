import asyncio

import aiohttp
import pytest
from aiohttp import web
from skylight_addon.ha import HAClient, HAError, watched_entities


async def wait_for(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_native_auth_state_events_disconnect_and_no_control_retry(aiohttp_server):
    calls = []
    sockets = []
    watched = []

    async def websocket(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        sockets.append(ws)
        await ws.send_json({"type": "auth_required"})
        assert await ws.receive_json() == {"type": "auth", "access_token": "private-test-token"}
        await ws.send_json({"type": "auth_ok"})
        async for frame in ws:
            message = frame.json()
            kind = message["type"]
            results = {
                "subscribe_events": None,
                "subscribe_entities": None,
                "get_services": {"light": {"toggle": {}}},
                "config/entity_registry/list": [
                    {"entity_id": "light.test", "platform": "philips_skylight"},
                    {"entity_id": "light.kitchen", "platform": "hue"},
                ],
            }
            if kind == "call_service":
                calls.append(message)
                await ws.close()
                break
            await ws.send_json(
                {"id": message["id"], "type": "result", "success": True, "result": results[kind]}
            )
            if kind == "subscribe_entities":
                watched.append((message["id"], message["entity_ids"]))
                state = {"s": "on", "a": {"effect": "Focus", "friendly_name": "Skylight"}}
                await ws.send_json(
                    {"id": message["id"], "type": "event", "event": {"a": {"light.test": state}}}
                )
        return ws

    async def entries(request):
        assert request.headers["Authorization"] == "Bearer private-test-token"
        return web.json_response([])

    app = web.Application()
    app.router.add_get("/websocket", websocket)
    app.router.add_get("/api/config/config_entries/entry", entries)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as session:
        client = HAClient(
            session,
            "private-test-token",
            str(server.make_url("/api")),
            str(server.make_url("/websocket")).replace("http://", "ws://"),
        )
        await client.start()
        try:
            await wait_for(lambda: client.ready)
            # Only the Skylight entity is watched, not every entity in the house.
            subscription, entity_ids = watched[-1]
            assert entity_ids == ["light.test"]
            assert client.states["light.test"]["state"] == "on"
            await sockets[-1].send_json(
                {
                    "id": subscription,
                    "type": "event",
                    "event": {
                        "c": {
                            "light.test": {
                                "+": {"s": "off", "a": {"last_command": "toggle"}},
                                "-": {"a": ["effect"]},
                            }
                        }
                    },
                }
            )
            await wait_for(lambda: client.states["light.test"]["state"] == "off")
            assert client.states["light.test"]["attributes"] == {
                "friendly_name": "Skylight",
                "last_command": "toggle",
            }
            await sockets[-1].send_json(
                {"id": subscription, "type": "event", "event": {"r": ["light.test"]}}
            )
            await wait_for(lambda: "light.test" not in client.states)
            with pytest.raises(HAError, match="not retried"):
                await client.call("light", "toggle", "light.test")
            await wait_for(lambda: len(sockets) >= 2 and client.ready)
            assert len(calls) == 1
        finally:
            await client.close()


def test_watched_entities_cover_skylight_and_esphome_sensors_only():
    registry = [
        {"entity_id": "light.skylight", "platform": "philips_skylight"},
        {"entity_id": "button.skylight_focus", "platform": "philips_skylight"},
        {"entity_id": "sensor.proxy_ble_adv_proxy_name", "platform": "esphome"},
        {"entity_id": "switch.proxy_restart", "platform": "esphome"},
        {"entity_id": "sensor.disabled", "platform": "esphome", "disabled_by": "user"},
        {"entity_id": "sensor.weather", "platform": "met"},
    ]
    assert watched_entities(registry) == {
        "light.skylight",
        "button.skylight_focus",
        "sensor.proxy_ble_adv_proxy_name",
    }
