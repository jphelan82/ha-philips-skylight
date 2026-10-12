"""Exercise the real light platform, entity actions, and unload lifecycle."""

import pytest
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
    assert hass.states.get(entity_id).state == "unknown"
    await hass.services.async_call(
        DOMAIN, "set_assumed_power", {"entity_id": entity_id, "is_on": False}, blocking=True
    )
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id, "effect": "Focus"}, blocking=True
    )
    assert hass.states.get(entity_id).state == "on"
    assert hass.states.get(entity_id).attributes["effect"] == "Focus"
    assert len(calls) == 2
    # Own packets relayed by the panel must not toggle an already updated entity.
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
            # Receiving a relay copy does not alter the entity a second time.
            hass.bus.async_fire(RECEIVE_EVENT, {"raw": raw})
            await hass.async_block_till_done()
            assert hass.states.get(entity_id) == state
    assert len(calls) == 2
    with pytest.raises(HomeAssistantError, match="may replace"):
        await hass.services.async_call(
            DOMAIN, "pair_transmitter", {"entity_id": entity_id, "confirm": False}, blocking=True
        )
    assert len(calls) == 2

    async def no_wait(seconds):
        pass

    with monkeypatch.context() as timing:
        timing.setattr("custom_components.philips_skylight.controller.asyncio.sleep", no_wait)
        await hass.services.async_call(
            DOMAIN, "pair_transmitter", {"entity_id": entity_id, "confirm": True}, blocking=True
        )
    assert len(calls) == 32
    assert hass.states.get(entity_id).state == "unknown"
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
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
    assert registry.async_get(entity_id).config_entry_id == entry.entry_id
    controller = hass.data[DOMAIN][entry.entry_id]
    assert await controller.sequence.async_next() == 256
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
    assert DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]
