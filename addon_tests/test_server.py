from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from skylight_addon.ha import HAError
from skylight_addon.server import Panel

ROOT = Path(__file__).resolve().parents[1] / "philips_skylight/app"


class FakeHA:
    ready = True
    error = None
    entries = []
    services = {"esphome": {"proxy_adv_svc_v1": {}}}
    registry = [
        {
            "platform": "philips_skylight",
            "unique_id": "factory_mesh_7ffe_light",
            "entity_id": "light.renamed",
        },
        {
            "platform": "philips_skylight",
            "unique_id": "factory_mesh_7ffe_rest",
            "entity_id": "button.renamed_scene",
        },
    ]
    states = {
        "light.renamed": {
            "state": "on",
            "attributes": {"integration_version": "0.2.0", "power_synchronized": True},
        },
        "sensor.proxy_ble_adv_proxy_name": {"state": "proxy"},
    }

    def __init__(self):
        self.calls = []

    async def call(self, *args, **kwargs):
        self.calls.append((args, kwargs))

    async def configure(self, *args):
        self.calls.append((args, {}))


@pytest.fixture
def panel():
    installer = SimpleNamespace(version="0.2.0", pending_restart=False, installed=lambda: True)
    return Panel(FakeHA(), installer, ROOT, allowed_ips={"127.0.0.1"})


async def test_ingress_rejects_forged_forwarded_ip(aiohttp_client, panel):
    panel.allowed_ips = {"172.30.32.2"}
    client = await aiohttp_client(panel.app())
    response = await client.get("/api/status", headers={"X-Forwarded-For": "172.30.32.2"})
    assert response.status == 403


async def test_actions_require_page_session_and_use_registered_entities(aiohttp_client, panel):
    client = await aiohttp_client(panel.app())
    response = await client.post("/api/action", json={"action": "toggle"})
    assert response.status == 403
    assert not panel.ha.calls
    response = await client.get("/", headers={"X-Ingress-Path": "/api/hassio_ingress/session"})
    markup = await response.text()
    assert '<base href="/api/hassio_ingress/session/">' in markup
    assert panel.csrf in markup
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    response = await client.post(
        "/api/action",
        json={"action": "scene", "effect": "Rest"},
        headers={"X-Skylight-CSRF": panel.csrf},
    )
    assert response.status == 200
    assert panel.ha.calls == [(("button", "press", "button.renamed_scene"), {})]


async def test_pairing_confirmation_and_action_allowlist(panel):
    with pytest.raises(ValueError, match="Confirm"):
        await panel.perform({"action": "pair", "confirm": False})
    assert not panel.ha.calls
    await panel.perform({"action": "pair", "confirm": True})
    assert panel.ha.calls == [
        (("philips_skylight", "pair_transmitter", "light.renamed"), {"confirm": True})
    ]
    with pytest.raises(ValueError, match="Unknown"):
        await panel.perform({"action": "call_any_service", "service": "lock.unlock"})
    with pytest.raises(ValueError, match="Specify"):
        await panel.perform({"action": "sync_power", "is_on": "false"})


async def test_ambiguous_failure_is_not_retried(panel, aiohttp_client):
    async def fail(*args, **kwargs):
        panel.ha.calls.append((args, kwargs))
        raise HAError("Result uncertain")

    panel.ha.call = fail
    client = await aiohttp_client(panel.app())
    response = await client.post(
        "/api/action", json={"action": "toggle"}, headers={"X-Skylight-CSRF": panel.csrf}
    )
    assert response.status == 400
    assert len(panel.ha.calls) == 1


async def test_stale_integration_blocks_controls_and_setup(panel):
    panel.installer.pending_restart = True
    with pytest.raises(ValueError, match="Restart"):
        await panel.perform({"action": "toggle"})
    assert not panel.ha.calls


async def test_dashboard_download_resolves_renamed_entities_and_keeps_corrections_local(
    aiohttp_client, panel
):
    commands = [
        "dim_down",
        "dim_up",
        "Refresh",
        "Energize",
        "Focus",
        "Relax",
        "Rest",
        "Auto rhythm",
        "record_panel_on",
        "record_panel_off",
    ]
    panel.ha.registry = [
        panel.ha.registry[0],
        *[
            {
                "platform": "philips_skylight",
                "unique_id": f"factory_mesh_7ffe_{command.lower().replace(' ', '_')}",
                "entity_id": f"button.custom_{index}",
            }
            for index, command in enumerate(commands)
        ],
        {
            "platform": "philips_skylight",
            "unique_id": "factory_mesh_7ffe_recorded_scene",
            "entity_id": "select.observed_scene",
        },
        {
            "platform": "philips_skylight",
            "unique_id": "factory_mesh_7ffe_state_correction",
            "entity_id": "switch.edit_panel",
        },
    ]
    client = await aiohttp_client(panel.app())
    response = await client.get("/api/dashboard-card")
    assert response.status == 200
    content = await response.text()
    assert "light.renamed" in content
    assert "select.observed_scene" in content
    assert "button.philips_skylight" not in content
    card = yaml.safe_load(content)
    assert card["type"] == "vertical-stack"
    assert "switch.edit_panel" in content

    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    normal, correction = card["cards"][1:]
    assert normal["conditions"] == [
        {"condition": "state", "entity": "switch.edit_panel", "state_not": "on"}
    ]
    assert correction["conditions"] == [
        {"condition": "state", "entity": "switch.edit_panel", "state": "on"}
    ]
    normal_actions = [item for item in walk(normal) if "perform_action" in item]
    assert "light.toggle" in {item["perform_action"] for item in normal_actions}
    assert not {"light.turn_on", "light.turn_off"} & {
        item["perform_action"] for item in normal_actions
    }
    # Correction view has no physical controls; only the two record buttons,
    # the scene-recording select, and a switch for returning to normal controls.
    correction_actions = [item for item in walk(correction) if "perform_action" in item]
    assert {item["perform_action"] for item in correction_actions} == {
        "button.press",
        "select.select_option",
        "switch.turn_off",
    }
    assert {
        item["target"]["entity_id"]
        for item in correction_actions
        if item["perform_action"] == "button.press"
    } == {"button.custom_8", "button.custom_9"}
    for effect in ("Refresh", "Energize", "Focus", "Relax", "Rest", "Auto rhythm"):
        choices = [
            item
            for item in walk(normal)
            if item.get("type") == "conditional"
            and any(
                condition.get("entity") == "select.observed_scene"
                and effect in (condition.get("state"), condition.get("state_not"))
                for condition in item["conditions"]
            )
        ]
        assert len(choices) == 2
        for choice in choices:
            selected = "state" in choice["conditions"][0]
            assert choice["card"]["color"] == ("blue" if selected else "grey")
    assert not panel.ha.calls
    panel.ha.registry[-1]["disabled_by"] = "user"
    response = await client.get("/api/dashboard-card")
    assert response.status == 400
