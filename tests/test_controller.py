import asyncio
import logging
from types import SimpleNamespace

import pytest
from homeassistant.core import Event
from homeassistant.exceptions import HomeAssistantError

from custom_components.philips_skylight.const import (
    CONF_PROXY_ENTITY,
    CONF_TRANSMIT_SERVICE,
    OUTAGE_GRACE,
    RECEIVE_EVENT,
)
from custom_components.philips_skylight.controller import SkylightController
from custom_components.philips_skylight.light import SkylightLight
from custom_components.philips_skylight.protocol import identify_command, pairing_payload

DATA = {
    CONF_TRANSMIT_SERVICE: "skylight_proxy_adv_svc_v1",
    CONF_PROXY_ENTITY: "sensor.proxy_ble_adv_proxy_name",
}


async def make_controller(hass):
    controller = SkylightController(hass, DATA)
    await controller.sequence.async_load()
    return controller


def proxy_online(hass):
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "skylight-proxy")


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


async def test_turn_on_with_effect_sends_only_the_mode_even_when_power_is_unknown(hass):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    for power in (None, False, True):
        controller.state.is_on = power
        calls.clear()
        await controller.async_power(True, "Relax")
        assert len(calls) == 1
        message = controller.codec.decode(bytes.fromhex(calls[0].data["raw"]))[0]
        assert identify_command(message.payload) == "Relax"
        assert controller.state.is_on is True
        assert controller.state.effect == "Relax"


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
    controller._proxy_changed(Event("state_changed", {"old_state": old, "new_state": None}))
    assert light.is_on is None
    assert light.effect is None


async def test_short_proxy_drop_keeps_state_but_long_outage_forgets_it(hass, monkeypatch):
    # No entity exists: the controller follows the proxy, so a disabled light changes nothing.
    controller = await make_controller(hass)
    receiver_setups = []

    async def setup_receiver():
        receiver_setups.append(True)

    controller.async_setup_receiver = setup_receiver
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "ready")
    unsubscribe = controller.async_track_proxy()
    clock = [1000.0]
    monkeypatch.setattr("custom_components.philips_skylight.controller.monotonic", lambda: clock[0])

    async def drop_for(seconds):
        hass.states.async_set(DATA[CONF_PROXY_ENTITY], "unavailable")
        await hass.async_block_till_done()
        assert controller.state.is_on is True  # Kept while the proxy is away.
        assert not controller.transmitter_ready
        clock[0] += seconds
        hass.states.async_set(DATA[CONF_PROXY_ENTITY], "ready")
        await hass.async_block_till_done()

    controller.state.is_on, controller.state.effect = True, "Relax"
    await drop_for(0.1)
    assert (controller.state.is_on, controller.state.effect) == (True, "Relax")
    assert len(receiver_setups) == 1  # Remote reception is set up again after each return.
    await drop_for(OUTAGE_GRACE + 1)
    assert (controller.state.is_on, controller.state.effect) == (None, None)
    assert len(receiver_setups) == 2
    unsubscribe()


async def test_light_refuses_unknown_effect_and_synchronizes_without_transmitting(hass):
    controller = await make_controller(hass)
    light = SkylightLight(controller, SimpleNamespace(data=DATA, title="Skylight"))
    light.hass = hass
    await controller.async_set_assumed_power(False)
    assert light.is_on is False
    with pytest.raises(HomeAssistantError, match="Unknown Skylight effect"):
        await light.async_turn_on(effect="invalid")
    assert controller.state.is_on is False


async def test_pairing_uses_durable_sequences(hass, monkeypatch):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    proxy_online(hass)
    controller = await make_controller(hass)
    controller.state.is_on = True
    controller.state.effect = "Focus"
    light = SkylightLight(controller, SimpleNamespace(data=DATA, title="Skylight"))
    light.hass = hass
    pauses = []

    async def no_wait(seconds):
        pauses.append(seconds)

    monkeypatch.setattr("custom_components.philips_skylight.controller.asyncio.sleep", no_wait)
    await controller.async_pair()
    assert light.extra_state_attributes["pairing_until"] is not None
    await controller.pairing_task
    assert light.extra_state_attributes["pairing_until"] is None
    assert len(calls) == 20  # Like the remote: twice a second for 10 seconds.
    assert pauses == [1 / 2] * 20
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


async def test_pairing_keeps_trying_through_failures_without_reporting_success(
    hass, monkeypatch, caplog
):
    calls = []

    async def no_wait(seconds):
        pass

    monkeypatch.setattr("custom_components.philips_skylight.controller.asyncio.sleep", no_wait)

    async def fail(call):
        calls.append(call)
        raise HomeAssistantError("proxy offline")

    hass.services.async_register("esphome", DATA[CONF_TRANSMIT_SERVICE], fail)
    proxy_online(hass)
    controller = await make_controller(hass)
    controller.state.is_on = True
    with caplog.at_level(logging.DEBUG, "custom_components.philips_skylight"):
        await controller.async_pair()
        await controller.pairing_task
    assert len(calls) == 20  # A short proxy drop does not end the burst.
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1  # Once per burst, not once per request.
    assert "proxy offline" in warnings[0].getMessage()
    assert controller.state.is_on is None
    assert controller.state.effect is None
    assert await controller.sequence.async_next() == 20


async def test_pairing_refuses_to_start_when_nothing_can_be_sent(hass):
    calls = []
    controller = await make_controller(hass)
    controller.state.is_on = True
    # The proxy is offline, then online without its advertising action.
    for online in (False, True):
        if online:
            proxy_online(hass)
        for start in (controller.async_pair, controller.async_unpair_all):
            with pytest.raises(HomeAssistantError, match="Cannot reach the Skylight proxy"):
                await start()
    assert controller.pairing_task is None
    assert controller.pairing_until is None
    assert controller.state.is_on is True
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    await controller.async_pair()
    while not calls:
        await asyncio.sleep(0)
    await controller.async_stop()


async def test_a_new_burst_keeps_its_state_when_the_old_burst_ends(hass):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    proxy_online(hass)
    controller = await make_controller(hass)
    await controller.async_pair()
    first = controller.pairing_task
    while not calls:
        await asyncio.sleep(0)
    await controller.async_unpair_all()
    second = controller.pairing_task
    until = controller.pairing_until
    # Let the cancelled first burst run its cleanup.
    await asyncio.gather(first, return_exceptions=True)
    assert first.cancelled()
    assert not second.done()
    assert controller.pairing_until == until
    assert controller.state.last_command == "unpair all"
    await controller.async_stop()
    assert second.cancelled()
    assert controller.pairing_until is None


async def test_stopped_controller_sends_nothing(hass):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    await controller.async_stop()
    with pytest.raises(HomeAssistantError, match="unloaded"):
        await controller.async_send("toggle")
    assert calls == []


async def test_toggle_with_an_effect_sends_the_effect(hass):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    light = SkylightLight(controller, SimpleNamespace(data=DATA, title="Skylight"))
    light.hass = hass
    controller.state.is_on = True
    await light.async_toggle(effect="Rest")
    (message,) = controller.codec.decode(bytes.fromhex(calls[0].data["raw"]))
    assert identify_command(message.payload) == "Rest"
    assert (controller.state.is_on, controller.state.effect) == (True, "Rest")
    calls.clear()
    await light.async_toggle()
    (message,) = controller.codec.decode(bytes.fromhex(calls[0].data["raw"]))
    assert identify_command(message.payload) == "toggle"


async def test_dim_hold_repeats_the_hold_command_at_the_remote_cadence(hass, monkeypatch):
    calls = []
    hass.services.async_register(
        "esphome", DATA[CONF_TRANSMIT_SERVICE], lambda call: calls.append(call)
    )
    controller = await make_controller(hass)
    pauses = []

    async def no_wait(seconds):
        pauses.append(seconds)

    monkeypatch.setattr("custom_components.philips_skylight.controller.asyncio.sleep", no_wait)
    await controller.async_dim("up", hold=3)
    assert len(calls) == 5
    assert pauses == [0.6] * 5
    for call in calls:
        (message,) = controller.codec.decode(bytes.fromhex(call.data["raw"]))
        assert message.payload[4:] == bytes.fromhex("01031441")
    assert controller.state.last_command == "dim_up"
    calls.clear()
    await controller.async_dim("down")
    (message,) = controller.codec.decode(bytes.fromhex(calls[0].data["raw"]))
    assert message.payload[4:] == bytes.fromhex("01001441")  # A tap is one step.
