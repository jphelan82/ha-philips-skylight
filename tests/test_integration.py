"""Exercise the real light platform, entity actions, and unload lifecycle."""

import sys
from pathlib import Path

import pytest
import voluptuous as vol
from homeassistant import loader
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.philips_skylight.config_flow import SkylightConfigFlow
from custom_components.philips_skylight.const import (
    CONF_PROXY_ENTITY,
    CONF_TRANSMIT_SERVICE,
    DOMAIN,
    EFFECTS,
    RECEIVE_EVENT,
)
from custom_components.philips_skylight.protocol import MeshCodec, command_payload

# The add-on names integration entities by unique ID; keep both sides in step.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "philips_skylight/app"))
import skylight_addon  # noqa: E402
from skylight_addon.server import CARD_ENTITIES, LIGHT_ID  # noqa: E402

DATA = {
    CONF_NAME: "Philips Skylight",
    CONF_TRANSMIT_SERVICE: "esphome_web_ece638_adv_svc_v1",
    CONF_PROXY_ENTITY: "sensor.proxy_ble_adv_proxy_name",
}


async def test_config_flow_requires_transmitter(hass):
    flow = SkylightConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    result = await flow.async_step_user()
    assert result["type"] == "abort"
    assert result["reason"] == "no_transmitter"


async def test_config_flow_creates_entry_with_online_transmitter(hass):
    hass.services.async_register("esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: None)
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "esphome-web-ece638")
    flow = SkylightConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}
    form = await flow.async_step_user()
    assert form["type"] == "form"
    result = await flow.async_step_user(DATA)
    assert result["type"] == "create_entry"
    assert result["data"] == DATA


async def test_real_platform_setup_actions_and_unload(hass, monkeypatch):
    loader.async_setup(hass)
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)

    # The ESPHome transport is represented by its real service interface. Avoid
    # opening sockets to a physical proxy or installing network integrations.
    async def transport_is_already_loaded(*args):
        return None

    monkeypatch.setattr("homeassistant.setup.async_process_deps_reqs", transport_is_already_loaded)
    monkeypatch.setattr(
        "homeassistant.config_entries.async_process_deps_reqs", transport_is_already_loaded
    )
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "esphome-web-ece638")
    entry = ConfigEntry(
        domain=DOMAIN,
        title="Philips Skylight",
        data=DATA,
        options={},
        source="user",
        unique_id="factory_mesh_7ffe",
        version=1,
        minor_version=1,
        discovery_keys={},
        subentries_data=[],
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    lights = [
        entity.entity_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id and entity.domain == "light"
    ]
    assert len(lights) == 1
    entity_id = lights[0]
    recorded_scene = registry.async_get_entity_id(
        "select", DOMAIN, "factory_mesh_7ffe_recorded_scene"
    )
    assert recorded_scene
    assert hass.states.get(entity_id).state == "unknown"
    assert hass.states.get(recorded_scene).state == "Unknown"
    skylight_ids = {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert {LIGHT_ID, *CARD_ENTITIES.values()} <= skylight_ids
    assert skylight_addon.EFFECTS == EFFECTS
    assert hass.states.get(entity_id).attributes["effect_list"] == list(skylight_addon.EFFECTS)
    await hass.services.async_call(
        DOMAIN, "set_assumed_power", {"entity_id": entity_id, "is_on": False}, blocking=True
    )
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id, "effect": "Focus"}, blocking=True
    )
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(entity_id).attributes["effect"] == "Focus"
    assert hass.states.get(recorded_scene).state == "Focus"
    assert len(calls) == 1
    # Own packets relayed by the panel must not change an already updated entity.
    hass.bus.async_fire(RECEIVE_EVENT, {"raw": calls[0].data["raw"]})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    # A second remote updates the real entity via authenticated receive events,
    # without echoing any command back to the panel.
    with monkeypatch.context() as sender:
        sender.setattr("custom_components.philips_skylight.protocol.SOURCE", 0x1234)
        codec = MeshCodec()
        commands = ["toggle", "toggle", *EFFECTS, "dim_down", "dim_up"]
        for sequence, command in enumerate(commands):
            raw = codec.encode(command_payload(command, 0x80 + sequence), sequence).hex()
            hass.bus.async_fire(RECEIVE_EVENT, {"raw": raw})
            await hass.async_block_till_done()
            state = hass.states.get(entity_id)
            assert state.state == ("off" if sequence == 0 else "on")
            assert state.attributes["last_command"] == command
            if command in EFFECTS:
                assert state.attributes["effect"] == command
                assert hass.states.get(recorded_scene).state == command
            # Receiving a relay copy does not alter the entity a second time.
            hass.bus.async_fire(RECEIVE_EVENT, {"raw": raw})
            await hass.async_block_till_done()
            assert hass.states.get(entity_id) == state
    assert len(calls) == 1
    with pytest.raises(vol.Invalid, match="may replace"):
        await hass.services.async_call(
            DOMAIN, "pair_transmitter", {"entity_id": entity_id, "confirm": False}, blocking=True
        )
    assert len(calls) == 1

    async def no_wait(seconds):
        pass

    with monkeypatch.context() as timing:
        timing.setattr("custom_components.philips_skylight.controller.asyncio.sleep", no_wait)
        await hass.services.async_call(
            DOMAIN, "pair_transmitter", {"entity_id": entity_id, "confirm": True}, blocking=True
        )
    assert len(calls) == 31
    assert hass.states.get(entity_id).state == "unknown"
    assert hass.states.get(recorded_scene).state == "Unknown"
    # Native dashboard correction entities update only the recorded state.
    for is_on in (True, False):
        power = "on" if is_on else "off"
        sync_button = registry.async_get_entity_id(
            "button", DOMAIN, f"factory_mesh_7ffe_record_panel_{power}"
        )
        assert sync_button
        await hass.services.async_call("button", "press", {"entity_id": sync_button}, blocking=True)
        assert hass.states.get(entity_id).state == power
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": recorded_scene, "option": "Rest"},
            blocking=True,
        )
        assert hass.states.get(recorded_scene).state == "Rest"
        assert hass.states.get(entity_id).attributes["assumed_effect"] == "Rest"
        assert hass.states.get(entity_id).state == power
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": recorded_scene, "option": "Unknown"},
            blocking=True,
        )
        assert hass.states.get(recorded_scene).state == "Unknown"
        assert hass.states.get(entity_id).attributes["assumed_effect"] is None
        assert len(calls) == 31
    with pytest.raises(HomeAssistantError, match="not valid"):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": recorded_scene, "option": "invalid"},
            blocking=True,
        )
    assert hass.states.get(recorded_scene).state == "Unknown"
    assert len(calls) == 31
    correction_mode = registry.async_get_entity_id(
        "switch", DOMAIN, "factory_mesh_7ffe_state_correction"
    )
    assert correction_mode
    assert hass.states.get(correction_mode).state == "off"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": correction_mode}, blocking=True
    )
    assert hass.states.get(correction_mode).state == "on"
    assert hass.states.get(entity_id).state == "off"
    assert hass.states.get(recorded_scene).state == "Unknown"
    assert len(calls) == 31
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
    assert hass.states.get(recorded_scene).state == "unavailable"
    assert hass.states.get(correction_mode).state == "on"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": correction_mode}, blocking=True
    )
    assert hass.states.get(correction_mode).state == "off"
    assert len(calls) == 31
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "esphome-web-ece638")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unknown"
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {**DATA, CONF_NAME: "Renamed Skylight"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.title == "Renamed Skylight"
    assert hass.states.get(correction_mode).state == "off"
    assert registry.async_get(entity_id).config_entry_id == entry.entry_id
    controller = entry.runtime_data
    assert await controller.sequence.async_next() == 256
    with pytest.raises(vol.Invalid, match="Skip the sequence only"):
        await hass.services.async_call(
            DOMAIN, "skip_sequence", {"entity_id": entity_id, "confirm": False}, blocking=True
        )
    await hass.services.async_call(
        DOMAIN, "skip_sequence", {"entity_id": entity_id, "confirm": True}, blocking=True
    )
    assert await controller.sequence.async_next() == 512 + 0x100000
    assert len(calls) == 31
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
