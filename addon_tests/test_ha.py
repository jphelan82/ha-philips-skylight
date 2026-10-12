import asyncio

import aiohttp
import pytest
from aiohttp import web
from skylight_addon.ha import HAClient, HAError


async def wait_for(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_native_auth_state_events_disconnect_and_no_control_retry(aiohttp_server):
    calls = []
    sockets = []

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
                "get_states": [{"entity_id": "light.test", "state": "on"}],
                "get_services": {"light": {"toggle": {}}},
                "config/entity_registry/list": [],
            }
            if kind == "call_service":
                calls.append(message)
                await ws.close()
                break
            await ws.send_json(
                {"id": message["id"], "type": "result", "success": True, "result": results[kind]}
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
            assert client.states["light.test"]["state"] == "on"
            await sockets[-1].send_json(
                {
                    "type": "event",
                    "event": {
                        "event_type": "state_changed",
                        "data": {
                            "entity_id": "light.test",
                            "new_state": {"state": "off"},
                        },
                    },
                }
            )
            await wait_for(lambda: client.states["light.test"]["state"] == "off")
            with pytest.raises(HAError, match="not retried"):
                await client.call("light", "toggle", "light.test")
            await wait_for(lambda: len(sockets) >= 2 and client.ready)
            assert len(calls) == 1
        finally:
            await client.close()
