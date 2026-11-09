"""Status behavior with a real HA bus; radio responses are injected after decoding."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import Event

from custom_components.philips_skylight import controller as module
from custom_components.philips_skylight.const import (
    CONF_PROXY_ENTITY,
    CONF_TRANSMIT_SERVICE,
    RECEIVE_EVENT,
    SOURCE,
)
from custom_components.philips_skylight.protocol import MeshMessage


@pytest.fixture
async def rig(hass, monkeypatch):
    controller = module.SkylightController(hass, {
        CONF_PROXY_ENTITY: "sensor.status_test_proxy",
        CONF_TRANSMIT_SERVICE: "status_test_adv_svc_v1",
    })
    await controller.sequence.async_load()
    hass.states.async_set(controller.proxy_entity, "online")
    hass.services.async_register("esphome", controller.service, lambda call: None)
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(module, "monotonic", lambda: clock.now)
    controller._async_transmit_locked = AsyncMock()

    def receive(on=True, sequence=1, source=module.STATUS_SOURCE, destination=SOURCE):
        message = MeshMessage(source, destination, sequence, 7, b"\x82\x04" + bytes([on]))
        monkeypatch.setattr(controller.codec, "decode", lambda raw: [message])
        controller.receive(Event(RECEIVE_EVENT, {"raw": "00"}))

    yield controller, clock, receive
    await controller.async_stop()


@pytest.mark.parametrize("physical", [False, True])
async def test_get_corrects_wrong_assumption(rig, physical):
    controller, clock, receive = rig
    await controller.async_set_assumed_power(not physical)
    assert await controller.async_test_onoff_get()
    receive(physical)
    assert controller.state.is_on is physical
    assert controller._async_transmit_locked.call_args.kwargs == {"repeat": 1}


async def test_wrong_addresses_late_and_replayed_status_do_not_change_power(rig):
    controller, clock, receive = rig
    controller.state.is_on = False
    await controller.async_test_onoff_get()
    receive(source=123)
    receive(destination=123)
    assert controller.state.is_on is False
    clock.now += 4
    receive(sequence=10)  # Late, but remember its sequence.
    await controller.async_test_onoff_get()
    receive(sequence=10)
    receive(sequence=9)
    assert controller.state.is_on is False
    receive(sequence=11)
    assert controller.state.is_on is True


async def test_status_during_toggle_send_cannot_reverse_assumption(rig):
    controller, clock, receive = rig
    controller.state.is_on = False
    await controller.async_test_onoff_get()

    async def transmit(*args, **kwargs):
        receive(True)

    controller._async_transmit_locked.side_effect = transmit
    await controller.async_send("toggle")
    assert controller.state.is_on is True


async def test_overlapping_gets_coalesce_even_after_fast_response(rig):
    controller, clock, receive = rig
    assert await controller.async_test_onoff_get()
    receive()
    assert not await controller.async_test_onoff_get()
    assert controller._async_transmit_locked.await_count == 1
    clock.now += 3
    assert await controller.async_test_onoff_get()


async def test_missing_answer_and_offline_proxy_preserve_power(rig):
    controller, clock, receive = rig
    controller.state.is_on = True
    await controller.async_test_onoff_get()
    clock.now += 4
    receive(False)
    assert controller.state.is_on is True
    controller.hass.states.async_set(controller.proxy_entity, "unavailable")
    with pytest.raises(module.HomeAssistantError):
        await controller.async_test_onoff_get()
    assert controller.state.is_on is True
    assert controller._async_transmit_locked.await_count == 1


async def test_periodic_poll_waits_thirty_seconds(rig, monkeypatch):
    controller, clock, receive = rig
    pauses = []

    async def sleep(delay):
        pauses.append(delay)
        clock.now += delay

    async def transmit(*args, **kwargs):
        controller.stopped = True

    monkeypatch.setattr(module, "asyncio", SimpleNamespace(sleep=sleep))
    controller._async_transmit_locked.side_effect = transmit
    await controller._async_poll_loop()
    assert pauses == [30]
    assert controller._async_transmit_locked.await_count == 1


async def test_verification_respects_newer_command_and_reuses_periodic_get(rig, monkeypatch):
    controller, clock, receive = rig
    controller._invalidate_pending_status()
    pauses = []

    async def sleep(delay):
        pauses.append(delay)
        clock.now += delay
        if len(pauses) == 1:
            controller._invalidate_pending_status()  # Another press during the wait.
        elif len(pauses) == 3:
            await controller.async_test_onoff_get()  # Periodic poll wins this turn.
            receive()

    monkeypatch.setattr(module, "asyncio", SimpleNamespace(sleep=sleep))
    await controller._async_verify_after_toggle()
    assert controller._async_transmit_locked.await_count == 1
    assert controller._last_status_query_at >= 110


async def test_toggle_while_verification_is_sending_gets_its_own_later_query(rig, monkeypatch):
    controller, clock, receive = rig
    controller._invalidate_pending_status()

    async def sleep(delay):
        clock.now += delay

    async def transmit(*args, **kwargs):
        if controller._async_transmit_locked.await_count == 1:
            controller._invalidate_pending_status()

    controller._async_transmit_locked.side_effect = transmit
    monkeypatch.setattr(module, "asyncio", SimpleNamespace(sleep=sleep))
    await controller._async_verify_after_toggle()
    assert controller._async_transmit_locked.await_count == 2
    assert clock.now == 110


async def test_background_tasks_stop_on_unload(rig, monkeypatch):
    controller, clock, receive = rig
    monkeypatch.setattr(module, "ENABLE_BACKGROUND_QUERIES", True)
    unsubscribe = controller.async_subscribe()
    controller._invalidate_pending_status()
    controller._schedule_toggle_verification()
    tasks = tuple(controller.tasks)
    await asyncio.sleep(0)
    await controller.async_stop()
    unsubscribe()
    assert len(tasks) == 2
    assert all(task.done() for task in tasks)
    controller._async_transmit_locked.assert_not_awaited()
