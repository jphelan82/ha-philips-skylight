import json
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


async def test_container_health_check_reaches_only_the_health_endpoint(aiohttp_client, panel):
    panel.allowed_ips = {"172.30.32.2"}
    client = await aiohttp_client(panel.app())
    response = await client.get("/health")
    assert response.status == 200
    assert (await response.json())["ok"] is True
    for path in ("/", "/api/status", "/api/firmware"):
        assert (await client.get(path)).status == 403


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
    # Once setup has succeeded, pairing again is refused: it can drop the remote.
    with pytest.raises(ValueError, match="already paired"):
        await panel.perform({"action": "pair", "confirm": True})
    assert not panel.ha.calls
    panel.first_setup = True
    await panel.perform({"action": "pair", "confirm": True})
    assert panel.ha.calls == [
        (("philips_skylight", "pair_transmitter", "light.renamed"), {"confirm": True})
    ]
    with pytest.raises(ValueError, match="Confirm that the panel ignores"):
        await panel.perform({"action": "skip_sequence"})
    await panel.perform({"action": "skip_sequence", "confirm": True})
    assert panel.ha.calls[-1] == (
        ("philips_skylight", "skip_sequence", "light.renamed"), {"confirm": True}
    )
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
        "set_rhythm_start",
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

    normal, correction = card["cards"]
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
    lit_when = {"condition": "state", "entity": "light.renamed", "state": "on"}
    unlit_when = {"condition": "state", "entity": "light.renamed", "state_not": "on"}
    for effect in ("Refresh", "Energize", "Focus", "Relax", "Rest", "Auto rhythm"):
        is_mode = {"condition": "state", "entity": "select.observed_scene", "state": effect}
        not_mode = {"condition": "state", "entity": "select.observed_scene", "state_not": effect}
        choices = [
            item
            for item in walk(normal)
            if item.get("type") == "conditional"
            and item["card"].get("entity", "").startswith("button.")
            and effect in json.dumps(item["conditions"])
        ]
        lit, unlit = choices
        # The recorded mode lights up in its own color, but only while the panel is on.
        assert lit["conditions"] == [is_mode, lit_when]
        assert lit["card"]["color"] != "grey"
        assert unlit["conditions"] == [{"condition": "or", "conditions": [not_mode, unlit_when]}]
        assert unlit["card"]["color"] == "grey"
    # A hold on a dim tile works from its icon too, where a thumb lands on a phone.
    held = [item for item in walk(normal) if item.get("hold_action")]
    assert len(held) == 2
    for item in held:
        assert item["hold_action"]["perform_action"] == "philips_skylight.dim"
        assert item["icon_hold_action"] == item["hold_action"]
    # The light's tile has one variant per mode in that mode's color, plus amber.
    hero = [
        item
        for item in walk(normal)
        if item.get("type") == "conditional" and item["card"].get("entity") == "light.renamed"
    ]
    assert len(hero) == 7
    assert [item["card"]["color"] for item in hero][-1] == "amber"
    assert len({item["card"]["color"] for item in hero}) == 6  # Focus shares amber.
    assert not panel.ha.calls
    panel.ha.registry[-1]["disabled_by"] = "user"
    response = await client.get("/api/dashboard-card")
    assert response.status == 400


async def test_friendly_proxy_setup_requires_explicit_save_and_does_not_create_dashboard(panel):
    panel.ha.registry = [
        *panel.ha.registry,
        {"entity_id": "sensor.proxy_ble_adv_proxy_name", "platform": "esphome"},
    ]
    assert len(panel.snapshot()["proxies"]) == 1
    assert not panel.ha.calls
    await panel.perform(
        {"action": "setup", "proxy": "sensor.proxy_ble_adv_proxy_name", "name": "Office"}
    )
    assert panel.ha.calls == [
        (("Office", "proxy_adv_svc_v1", "sensor.proxy_ble_adv_proxy_name"), {})
    ]
    assert not panel.snapshot()["first_setup"]
    with pytest.raises(ValueError, match="available Skylight proxy"):
        await panel.perform({"action": "setup", "proxy": "sensor.missing"})


async def test_card_export_and_initial_matching_never_send_light_commands(panel, aiohttp_client):
    from skylight_addon.server import CARD_ENTITIES

    panel.ha.registry = [
        {"entity_id": entity, "unique_id": unique, "platform": "philips_skylight"}
        for entity, unique in CARD_ENTITIES.items()
    ]
    panel.ha.states = {"light.philips_skylight": panel.ha.states["light.renamed"]}
    client = await aiohttp_client(panel.app())
    response = await client.get("/api/dashboard-card")
    assert response.status == 200
    card = yaml.safe_load(await response.text())
    assert len(card["cards"]) == 2
    assert card == panel.card_config()
    await panel.perform({"action": "sync_state", "power": "off", "effect": "Unknown"})
    assert panel.ha.calls == [
        (("button", "press", "button.philips_skylight_record_panel_off"), {}),
        (
            ("select", "select_option", "select.philips_skylight_recorded_scene"),
            {"option": "Unknown"},
        ),
    ]
    with pytest.raises(ValueError, match="Record the power"):
        await panel.perform({"action": "sync_state", "power": "on", "effect": "invented"})
    assert len(panel.ha.calls) == 2


async def test_first_setup_guidance_survives_restart_and_ends_after_state_matching(panel, tmp_path):
    from skylight_addon.server import CARD_ENTITIES

    panel.installer.data = tmp_path
    fresh = Panel(panel.ha, panel.installer, ROOT, allowed_ips={"127.0.0.1"})
    assert not fresh.snapshot()["first_setup"]  # Existing installs are not sent through pairing.
    fresh.ha.registry = [
        {"entity_id": "sensor.proxy_ble_adv_proxy_name", "platform": "esphome"},
    ]
    await fresh.perform({"action": "setup", "proxy": "sensor.proxy_ble_adv_proxy_name"})
    restarted = Panel(fresh.ha, panel.installer, ROOT, allowed_ips={"127.0.0.1"})
    assert restarted.snapshot()["first_setup"]
    restarted.ha.registry = [
        {"entity_id": entity, "unique_id": unique, "platform": "philips_skylight"}
        for entity, unique in CARD_ENTITIES.items()
    ]
    restarted.ha.states = {
        "light.philips_skylight": {"attributes": {"integration_version": "0.2.0"}}
    }
    await restarted.perform({"action": "sync_state", "power": "on", "effect": "Unknown"})
    final = Panel(restarted.ha, panel.installer, ROOT, allowed_ips={"127.0.0.1"})
    assert not final.snapshot()["first_setup"]
    assert [args[0] for args, _ in final.ha.calls] == ["Philips Skylight", "button", "select"]


async def test_remote_assisted_matching_records_only_power_and_finishes_setup(panel, tmp_path):
    panel.installer.data = tmp_path
    fresh = Panel(panel.ha, panel.installer, ROOT, allowed_ips={"127.0.0.1"})
    fresh.ha.states = {
        "light.renamed": {
            "state": "unknown",
            "attributes": {"integration_version": "0.2.0", "assumed_effect": "Focus"},
        }
    }
    await fresh.set_first_setup(True)
    await fresh.perform({"action": "sync_power", "is_on": True})
    assert fresh.ha.calls == [
        (("philips_skylight", "set_assumed_power", "light.renamed"), {"is_on": True})
    ]
    assert fresh.snapshot()["effect"] == "Focus"
    assert not Panel(fresh.ha, panel.installer, ROOT).first_setup


async def test_manual_mode_records_without_operating_light_or_establishing_power(panel):
    from skylight_addon.server import CARD_ENTITIES

    panel.ha.registry = [
        {"entity_id": entity, "unique_id": unique, "platform": "philips_skylight"}
        for entity, unique in CARD_ENTITIES.items()
    ]
    panel.ha.states = {
        "light.philips_skylight": {
            "state": "unknown", "attributes": {"integration_version": "0.2.0"}
        }
    }
    panel.first_setup = True
    for effect in ("Focus", "Unknown"):
        await panel.perform({"action": "sync_mode", "effect": effect})
    assert panel.ha.calls == [
        (("select", "select_option", "select.philips_skylight_recorded_scene"), {"option": effect})
        for effect in ("Focus", "Unknown")
    ]
    assert panel.first_setup
    assert not panel.snapshot()["power_synchronized"]
    with pytest.raises(ValueError, match="Choose a mode"):
        await panel.perform({"action": "sync_mode", "effect": "invalid"})
    assert len(panel.ha.calls) == 2


class SetupHA(FakeHA):
    """A Home Assistant with one compatible proxy and no Skylight entry yet."""

    def __init__(self, tracking=False):
        super().__init__()
        self.registry = [
            {
                "platform": "esphome",
                "entity_id": "sensor.proxy_ble_adv_proxy_name",
                "unique_id": "aa-ble_adv_proxy_name",
                "config_entry_id": "esphome-entry",
            }
        ]
        self.options = {"allow_service_calls": tracking, "subscribe_logs": False}
        self.set = []

    async def read_options(self, entry_id):
        assert entry_id == "esphome-entry"
        return dict(self.options)

    async def set_options(self, entry_id, changes):
        self.set.append((entry_id, changes))
        self.options.update(changes)

    async def panel_url(self, match):
        panel = {"title": "ESPHome Builder", "config": {"ingress": "5c53de3b_esphome"}}
        return "/5c53de3b_esphome" if match(panel) else None

    async def configure(self, *args):
        await super().configure(*args)
        self.registry = [
            *self.registry,
            {
                "platform": "philips_skylight",
                "unique_id": "factory_mesh_7ffe_light",
                "entity_id": "light.renamed",
            },
            *(
                {
                    "platform": "philips_skylight",
                    "unique_id": f"factory_mesh_7ffe_{name}",
                    "entity_id": f"button.skylight_{name}",
                }
                for name in ("set_rhythm_start", "rest")
            ),
        ]


@pytest.fixture
def setup_panel(tmp_path):
    installer = SimpleNamespace(
        version="0.2.0", pending_restart=False, installed=lambda: True, data=tmp_path / "data"
    )
    return Panel(SetupHA(), installer, ROOT, allowed_ips={"127.0.0.1"}, esphome_dir=tmp_path)


async def test_one_proxy_is_connected_without_asking_and_checks_are_cached(setup_panel):
    ha = setup_panel.ha
    setup_panel.schedule_checks()  # The first poll reads the settings.
    await setup_panel._check_task
    assert setup_panel.tracking is False
    assert setup_panel.device_builder == "/5c53de3b_esphome"
    setup_panel.schedule_checks()  # The next poll sets up the only proxy.
    await setup_panel._check_task
    expected = ("Philips Skylight", "proxy_adv_svc_v1", "sensor.proxy_ble_adv_proxy_name")
    assert ha.calls == [(expected, {})]
    assert setup_panel.first_setup is True
    setup_panel.schedule_checks()  # It never tries twice.
    assert setup_panel._check_task.done()
    assert len(ha.calls) == 1


async def test_tracking_is_turned_on_through_the_esphome_settings(setup_panel):
    await setup_panel.perform({"action": "allow_tracking"})
    assert setup_panel.ha.set == [("esphome-entry", {"allow_service_calls": True})]
    assert setup_panel.tracking is True


async def test_pairing_test_and_rhythm_start_press_the_right_buttons(setup_panel):
    ha = setup_panel.ha
    await setup_panel.perform({"action": "setup", "proxy": "sensor.proxy_ble_adv_proxy_name"})
    ha.calls.clear()
    await setup_panel.perform({"action": "test"})
    await setup_panel.perform({"action": "rhythm_start"})
    assert ha.calls == [
        (("light", "toggle", "light.renamed"), {}),
        (("button", "press", "button.skylight_set_rhythm_start"), {}),
    ]
    with pytest.raises(ValueError, match="what the panel did"):
        await setup_panel.perform({"action": "confirm_test", "result": True})
    ha.calls.clear()
    await setup_panel.perform({"action": "confirm_test", "result": "none"})
    assert setup_panel.first_setup is True
    assert ha.calls == []  # No answer about power means no record.
    await setup_panel.perform({"action": "confirm_test", "result": "off"})
    assert setup_panel.first_setup is True  # Setup ends after the mode step.
    assert ha.calls == [
        (("philips_skylight", "set_assumed_power", "light.renamed"), {"is_on": False})
    ]
    ha.calls.clear()
    with pytest.raises(ValueError, match="Unknown mode"):
        await setup_panel.perform({"action": "finish_setup", "effect": "Disco"})
    await setup_panel.perform({"action": "finish_setup", "effect": "Rest"})
    assert ha.calls == [(("button", "press", "button.skylight_rest"), {})]
    assert setup_panel.first_setup is False
    await setup_panel.perform({"action": "finish_setup"})  # Skip presses nothing.
    assert len(ha.calls) == 1


async def test_firmware_is_added_to_the_chosen_proxy(setup_panel, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "firmware").symlink_to(ROOT.parent / "firmware")
    setup_panel.root = root
    (tmp_path / "proxy.yaml").write_text("esphome:\n  name: proxy\n\nbluetooth_proxy:\n")
    snapshot = setup_panel.snapshot()
    node = {
        "file": "proxy.yaml",
        "node": "proxy",
        "has_skylight": False,
        "uses_package": False,
        "api_key": False,
    }
    assert snapshot["esphome_nodes"] == [node]
    assert snapshot["firmware"] is None  # The setup checklist handles a new proxy.
    result = await setup_panel.perform({"action": "prepare_firmware", "file": "proxy.yaml"})
    assert result["changed"] is True
    assert setup_panel.snapshot()["esphome_nodes"][0]["has_skylight"] is True


async def test_firmware_updates_cover_new_files_and_an_install(setup_panel, tmp_path):
    ha = setup_panel.ha
    ha.states = {name: dict(item) for name, item in ha.states.items()}  # Keep changes local.
    root = tmp_path / "root"
    root.mkdir()
    (root / "firmware").symlink_to(ROOT.parent / "firmware")
    setup_panel.root = root
    (tmp_path / "proxy.yaml").write_text("esphome:\n  name: proxy\n\nbluetooth_proxy:\n")
    await setup_panel.perform({"action": "prepare_firmware", "file": "proxy.yaml"})
    await setup_panel.check()
    firmware = setup_panel.snapshot()["firmware"]
    bundled = firmware["version"]
    assert bundled.isdigit()
    # The proxy reports no number: it runs firmware from before the number existed.
    assert firmware == {"status": "install", "version": bundled, "reported": [], "nodes": ["proxy"]}

    ha.states["sensor.proxy_skylight_firmware"] = {"state": bundled}
    assert setup_panel.snapshot()["firmware"]["status"] == "current"

    # An add-on update brings newer files than the ESPHome folder holds.
    (tmp_path / "skylight-transmitter.yaml").write_text("# older package\n")
    await setup_panel.check()
    assert setup_panel.snapshot()["firmware"]["status"] == "files"
    result = await setup_panel.perform({"action": "update_firmware"})
    assert result["changed"] is True
    await setup_panel.check()
    # The new files need an install when the proxy still reports the old number.
    ha.states["sensor.proxy_skylight_firmware"] = {"state": "0"}
    assert setup_panel.snapshot()["firmware"]["status"] == "install"
    ha.states["sensor.proxy_skylight_firmware"] = {"state": bundled}
    assert setup_panel.snapshot()["firmware"]["status"] == "current"

    # No message while the proxy is offline: it cannot take an install then.
    ha.states["sensor.proxy_skylight_firmware"] = {"state": "unavailable"}
    ha.states["sensor.proxy_ble_adv_proxy_name"]["state"] = "unavailable"
    assert setup_panel.snapshot()["firmware"]["status"] == "current"


async def test_pairing_burst_reports_seconds_left(setup_panel):
    from datetime import UTC, datetime, timedelta

    ha = setup_panel.ha
    await setup_panel.perform({"action": "setup", "proxy": "sensor.proxy_ble_adv_proxy_name"})
    until = datetime.now(UTC) + timedelta(seconds=9)
    ha.states["light.renamed"] = {
        "state": "unknown",
        "attributes": {"integration_version": "0.2.0", "pairing_until": until.isoformat()},
    }
    assert 7 <= setup_panel.snapshot()["pairing_remaining"] <= 9
    ha.calls.clear()
    await setup_panel.perform({"action": "pair", "confirm": True})
    assert ha.calls == [
        (("philips_skylight", "pair_transmitter", "light.renamed"), {"confirm": True}),
    ]
    with pytest.raises(ValueError, match="Unknown action"):
        await setup_panel.perform({"action": "stop_pairing"})
    ha.states["light.renamed"]["attributes"]["pairing_until"] = "not a time"
    assert setup_panel.snapshot()["pairing_remaining"] == 0


async def test_dim_hold_sends_one_hold_command_per_request(setup_panel):
    ha = setup_panel.ha
    await setup_panel.perform({"action": "setup", "proxy": "sensor.proxy_ble_adv_proxy_name"})
    ha.calls.clear()
    await setup_panel.perform({"action": "dim_hold", "direction": "up"})
    assert ha.calls == [
        (("philips_skylight", "dim", "light.renamed"), {"direction": "up", "hold": 0.6})
    ]
    with pytest.raises(ValueError, match="direction"):
        await setup_panel.perform({"action": "dim_hold", "direction": "sideways"})



async def test_start_over_unpairs_everything_then_reopens_pairing(panel):
    with pytest.raises(ValueError, match="Tick the box"):
        await panel.perform({"action": "unpair_all"})
    await panel.perform({"action": "unpair_all", "confirm": True})
    assert panel.ha.calls == [
        (("philips_skylight", "unpair_all_remotes", "light.renamed"), {"confirm": True})
    ]
    assert panel.first_setup is False
    await panel.perform({"action": "start_over"})
    assert panel.first_setup is True
    await panel.perform({"action": "pair", "confirm": True})  # Allowed again.
    assert panel.ha.calls[-1][0][1] == "pair_transmitter"
