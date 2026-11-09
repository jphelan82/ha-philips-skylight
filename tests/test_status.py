"""The panel's Generic OnOff Status, with replies built by the real mesh codec."""

import asyncio
import logging

import pytest
from homeassistant.core import Event
from homeassistant.exceptions import HomeAssistantError

from custom_components.philips_skylight import controller as module
from custom_components.philips_skylight.const import (
    CONF_PROXY_ENTITY,
    CONF_TRANSMIT_SERVICE,
    DESTINATION,
    RECEIVE_EVENT,
    SOURCE,
)
from custom_components.philips_skylight.protocol import (
    ONOFF_GET,
    command_payload,
    identify_command,
    onoff_status,
)

DATA = {
    CONF_TRANSMIT_SERVICE: "skylight_proxy_adv_svc_v1",
    CONF_PROXY_ENTITY: "sensor.proxy_ble_adv_proxy_name",
}
# The address that one owner's panel answers from. Others differ.
PANEL = 0x3CC2


def test_status_parser_reads_short_and_long_forms_only():
    assert onoff_status(b"\x82\x04\x01") is True
    assert onoff_status(b"\x82\x04\x00") is False
    # Long form: present, target, remaining time. The target wins.
    assert onoff_status(b"\x82\x04\x00\x01\x05") is True
    assert onoff_status(b"\x82\x04\x01\x00\x05") is False
    for payload in (b"\x82\x04", b"\x82\x04\x02", b"\x82\x04\x01\x00", b"\x82\x01", b""):
        assert onoff_status(payload) is None


class Rig:
    """A controller with an online proxy and a panel that can answer."""

    def __init__(self, hass, controller):
        self.hass = hass
        self.controller = controller
        self.sent = []
        self.messages = []
        # Answer each Get with this power from this address, or stay silent.
        self.answer: bool | None = None
        # Stay silent for this many Gets first, like a missed answer.
        self.miss = 0
        self.answer_from = PANEL
        self.panel_sequence = 100

    def reply(self, is_on: bool, source: int = PANEL, destination: int = SOURCE) -> None:
        self.panel_sequence += 1
        raw = self.controller.codec.encode(
            b"\x82\x04" + bytes([is_on]), self.panel_sequence, source, destination
        )
        self.controller.receive(Event(RECEIVE_EVENT, {"raw": raw.hex()}))

    def transmit(self, call) -> None:
        message = self.controller.codec.decode(bytes.fromhex(call.data["raw"]))[0]
        self.messages.append(message)
        self.sent.append(message.payload)
        if message.payload != ONOFF_GET or self.answer is None:
            return
        if self.miss:
            self.miss -= 1
            return
        # The panel answers while the proxy is still sending.
        self.reply(self.answer, self.answer_from)

    def gets(self) -> int:
        return self.sent.count(ONOFF_GET)


@pytest.fixture
async def rig(hass, monkeypatch):
    monkeypatch.setattr(module, "STATUS_WINDOW", 0.05)
    controller = module.SkylightController(hass, DATA)
    await controller.sequence.async_load()
    rig = Rig(hass, controller)
    hass.services.async_register("esphome", DATA[CONF_TRANSMIT_SERVICE], rig.transmit)
    hass.states.async_set(DATA[CONF_PROXY_ENTITY], "skylight-proxy")
    yield rig
    await controller.async_stop()


@pytest.mark.parametrize("physical", [False, True])
async def test_refresh_corrects_a_wrong_assumption(rig, physical):
    controller = rig.controller
    await controller.async_set_assumed_power(not physical)
    rig.answer = physical
    assert await controller.async_refresh_power() is True
    assert controller.state.is_on is physical
    assert rig.sent == [ONOFF_GET]


async def test_get_goes_from_this_sender_to_every_node(rig):
    await rig.controller.async_refresh_power()
    message = rig.messages[0]
    assert (message.source, message.destination, message.payload) == (
        SOURCE,
        DESTINATION,
        ONOFF_GET,
    )


async def test_any_panel_address_is_accepted(rig):
    rig.answer, rig.answer_from = True, 0x0042
    assert await rig.controller.async_refresh_power() is True
    assert rig.controller.state.is_on is True


async def test_silence_leaves_power_unchanged(rig):
    controller = rig.controller
    await controller.async_set_assumed_power(True)
    assert await controller.async_refresh_power() is False
    assert controller.state.is_on is True
    assert controller.status_request is None


async def test_unrequested_misaddressed_and_own_status_are_ignored(rig):
    controller = rig.controller
    await controller.async_set_assumed_power(False)
    rig.reply(True)  # No request is open.
    assert controller.state.is_on is False

    answer = controller.hass.loop.create_future()
    controller.status_request = (controller.power_changes, answer)
    rig.reply(True, destination=0x1234)  # Not addressed to this sender.
    rig.reply(True, source=SOURCE)  # This sender's own address.
    rig.reply(True, source=0x8001)  # A group address cannot answer.
    assert controller.state.is_on is False
    assert not answer.done()
    rig.reply(True)
    assert answer.result() is True
    assert controller.state.is_on is True


async def test_an_answer_older_than_a_toggle_is_ignored(rig):
    controller = rig.controller
    await controller.async_set_assumed_power(False)
    refresh = asyncio.ensure_future(controller.async_refresh_power())
    await asyncio.sleep(0)
    await controller.async_send("toggle")  # Waits for the Get to finish sending.
    assert controller.state.is_on is True
    rig.reply(False)  # Could describe the power from before the toggle.
    assert await refresh is False
    assert controller.state.is_on is True


async def test_a_remote_toggle_makes_an_open_answer_stale_and_schedules_a_check(rig):
    controller = rig.controller
    await controller.async_set_assumed_power(False)
    answer = controller.hass.loop.create_future()
    controller.status_request = (controller.power_changes, answer)
    controller.status_due = module.monotonic() + 1000
    remote = controller.codec.encode(command_payload("toggle", 0x80), 1, 0x7FFF)
    controller.receive(Event(RECEIVE_EVENT, {"raw": remote.hex()}))
    assert controller.state.is_on is True
    assert controller.status_due < module.monotonic() + 10
    rig.reply(False)
    assert answer.result() is False
    assert controller.state.is_on is True


async def test_status_during_pairing_does_not_set_power(rig):
    controller = rig.controller
    controller.pairing_until = object()
    rig.answer = True
    assert await controller.async_refresh_power() is True
    assert controller.state.is_on is None


async def test_offline_proxy_refuses_refresh_and_sends_nothing(rig):
    rig.hass.states.async_set(DATA[CONF_PROXY_ENTITY], "unavailable")
    with pytest.raises(HomeAssistantError, match="Cannot reach the Skylight proxy"):
        await rig.controller.async_refresh_power()
    assert rig.sent == []


async def test_turn_off_with_unknown_power_asks_the_panel_first(rig):
    controller = rig.controller
    rig.answer = False
    await controller.async_power(False)
    # The panel said off, so no toggle goes out.
    assert rig.sent == [ONOFF_GET]
    assert controller.state.is_on is False
    rig.answer = True
    controller.state.is_on = None
    await controller.async_power(False)
    assert [identify_command(p) for p in rig.sent[1:]] == [None, "toggle"]
    assert controller.state.is_on is False


async def test_turn_off_with_unknown_power_and_a_silent_panel_explains(rig):
    with pytest.raises(HomeAssistantError, match="did not report it"):
        await rig.controller.async_power(False)
    assert rig.sent == [ONOFF_GET] * module.STATUS_TRIES


async def test_a_missed_answer_gets_one_more_question(rig):
    controller = rig.controller
    await controller.async_set_assumed_power(True)
    rig.answer, rig.miss = False, 1
    assert await controller.async_refresh_power() is True
    assert rig.gets() == 2
    assert controller.state.is_on is False
    rig.sent.clear()
    rig.miss = 2  # Both questions missed.
    controller.state.is_on = True
    assert await controller.async_refresh_power() is False
    assert rig.gets() == 2
    assert controller.state.is_on is True


async def test_a_late_answer_is_logged_and_ignored(rig, caplog):
    controller = rig.controller
    await controller.async_set_assumed_power(True)
    assert await controller.async_refresh_power() is False
    caplog.set_level(logging.DEBUG, logger=module.__name__)
    rig.reply(False)  # Arrives after the wait.
    assert controller.state.is_on is True
    assert "outside the wait; ignored" in caplog.text
    assert "0x3CC2 reports power off" in caplog.text


async def test_status_loop_asks_after_a_toggle_and_stops_on_unload(rig, monkeypatch):
    monkeypatch.setattr(module, "STATUS_DELAY", 0.01)
    monkeypatch.setattr(module, "STATUS_INTERVAL", 1000)
    controller = rig.controller
    controller.request_status(1000)  # Nothing is due yet.
    controller.async_start_status()
    await asyncio.sleep(0.05)
    assert rig.gets() == 0

    controller.state.is_on = False
    rig.answer = False  # The toggle did not reach the panel.
    await controller.async_send("toggle")
    assert controller.state.is_on is True
    await asyncio.sleep(0.15)
    assert rig.gets() == 1
    assert controller.state.is_on is False

    await controller.async_stop()
    assert all(task.done() for task in controller.tasks)
    controller.request_status(0)
    await asyncio.sleep(0.05)
    assert rig.gets() == 1


async def test_status_loop_skips_while_the_proxy_is_offline(rig):
    controller = rig.controller
    rig.hass.states.async_set(DATA[CONF_PROXY_ENTITY], "unavailable")
    controller.request_status(0)
    controller.async_start_status()
    await asyncio.sleep(0.05)
    assert rig.sent == []
    # A skipped check waits a full interval, not a short delay.
    assert controller.status_due > module.monotonic() + module.STATUS_INTERVAL - 5
