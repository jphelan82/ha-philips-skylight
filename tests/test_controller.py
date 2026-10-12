import asyncio
from types import SimpleNamespace

import pytest
from homeassistant.core import Event
from homeassistant.exceptions import HomeAssistantError

from custom_components.philips_skylight.const import (
    CONF_PROXY_ENTITY,
    CONF_TRANSMIT_SERVICE,
    RECEIVE_EVENT,
)
from custom_components.philips_skylight.controller import SkylightController
from custom_components.philips_skylight.light import SkylightLight
from custom_components.philips_skylight.protocol import pairing_payload

DATA = {
    CONF_TRANSMIT_SERVICE: "esphome_web_ece638_adv_svc_v1",
    CONF_PROXY_ENTITY: "sensor.proxy_ble_adv_proxy_name",
}


async def make_controller(hass):
    controller = SkylightController(hass, DATA)
    await controller.sequence.async_load()
    return controller


async def test_unknown_power_requires_sync_and_same_power_is_noop(hass):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    with pytest.raises(HomeAssistantError, match="power is unknown"):
        await controller.async_power(True)
    assert calls == []
    controller.state.is_on = True
    await controller.async_power(True)
    assert calls == []
    await controller.async_power(False)
    assert len(calls) == 1
    assert controller.state.is_on is False
    raw = bytes.fromhex(calls[0].data["raw"])
    assert controller.codec.decode(raw)[0].source == 0x7FFE


async def test_concurrent_turn_on_calls_toggle_only_once(hass):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    controller.state.is_on = False
    await asyncio.gather(controller.async_power(True), controller.async_power(True))
    assert len(calls) == 1
    assert controller.state.is_on is True


async def test_transport_failure_consumes_sequence_but_does_not_retry_or_update_state(hass):
    calls = []

    async def fail(call):
        calls.append(call)
        raise HomeAssistantError("proxy offline")

    hass.services.async_register("esphome", DATA[CONF_TRANSMIT_SERVICE], fail)
    controller = await make_controller(hass)
    controller.state.is_on = False
    with pytest.raises(HomeAssistantError, match="proxy offline"):
        await controller.async_power(True)
    assert len(calls) == 1
    assert controller.state.is_on is False
    assert await controller.sequence.async_next() == 1


async def test_real_store_restart_skips_reserved_range(hass):
    controller = await make_controller(hass)
    assert await controller.sequence.async_next() == 0
    # New Store instance reads the persisted high watermark from disk.
    restarted = await make_controller(hass)
    assert await restarted.sequence.async_next() == 256


async def test_remote_event_and_proxy_outage(hass):
    controller = await make_controller(hass)
    light = SkylightLight(controller, SimpleNamespace(data=DATA, title="Skylight"))
    light.hass = hass
    controller.state.is_on = True
    event = Event(RECEIVE_EVENT, {"raw": "1a2a1bc5e03c8aceab4468d9d8e76f77efbb889cd1530fa6955cac"})
    controller.receive(event)
    assert light.is_on is False
    controller.receive(event)
    assert light.is_on is False
    controller.receive(Event(RECEIVE_EVENT, {"raw": "not hex"}))
    controller.state.effect = "Focus"
    old = hass.states.async_set(DATA[CONF_PROXY_ENTITY], "ready")
    light._proxy_changed(Event("state_changed", {"old_state": old, "new_state": None}))
    assert light.is_on is None
    assert light.effect is None


async def test_light_refuses_unknown_effect_and_synchronizes_without_transmitting(hass):
    controller = await make_controller(hass)
    light = SkylightLight(controller, SimpleNamespace(data=DATA, title="Skylight"))
    light.hass = hass
    await light.async_set_assumed_power(False)
    assert light.is_on is False
    with pytest.raises(HomeAssistantError, match="Unknown Skylight effect"):
        await light.async_turn_on(effect="invalid")
    assert controller.state.is_on is False


async def test_pairing_requires_confirmation_and_uses_durable_sequences(hass, monkeypatch):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    controller.state.is_on = True
    controller.state.effect = "Focus"
    light = SkylightLight(controller, SimpleNamespace(data=DATA, title="Skylight"))
    light.hass = hass
    with pytest.raises(HomeAssistantError, match="may replace"):
        await light.async_pair_transmitter(False)
    assert calls == []
    assert controller.state.is_on is True

    pauses = []

    async def no_wait(seconds):
        pauses.append(seconds)

    monkeypatch.setattr("custom_components.philips_skylight.controller.asyncio.sleep", no_wait)
    await light.async_pair_transmitter(True)
    assert len(calls) == 30
    assert pauses == [1 / 3] * 30
    for sequence, call in enumerate(calls):
        assert call.data["repeat"] == 1
        assert call.data["duration"] == 100
        (message,) = controller.codec.decode(bytes.fromhex(call.data["raw"]))
        assert message.source == 0x7FFE
        assert message.sequence == sequence
        assert message.payload == pairing_payload(0x80 + sequence)
    assert controller.state.is_on is None
    assert controller.state.effect is None
    restarted = await make_controller(hass)
    assert await restarted.sequence.async_next() == 256


async def test_pairing_stops_on_transport_failure_without_reporting_success(hass):
    calls = []

    async def fail(call):
        calls.append(call)
        raise HomeAssistantError("proxy offline")

    hass.services.async_register("esphome", DATA[CONF_TRANSMIT_SERVICE], fail)
    controller = await make_controller(hass)
    controller.state.is_on = True
    with pytest.raises(HomeAssistantError, match="proxy offline"):
        await controller.async_pair()
    assert len(calls) == 1
    assert controller.state.is_on is None
    assert controller.state.effect is None
    assert await controller.sequence.async_next() == 1
