"""Serialize commands and forward authenticated packets to an ESPHome proxy."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_TRANSMIT_SERVICE,
    DOMAIN,
    HOLD_INTERVAL,
    PAIRING_BURST,
    PAIRING_RATE,
    RECEIVE_EVENT,
    STORAGE_KEY,
)
from .model import AssumedState, RemoteTracker
from .protocol import MeshCodec, command_payload, pairing_payload, unpair_all_payload
from .sequence import SequenceAllocator

_LOGGER = logging.getLogger(__name__)


class SkylightController:
    def __init__(self, hass: HomeAssistant, data: dict) -> None:
        self.hass = hass
        self.service = data[CONF_TRANSMIT_SERVICE]
        self.codec = MeshCodec()
        self.state = AssumedState()
        self.state_correction = False
        self.remote = RemoteTracker()
        self.sequence = SequenceAllocator(Store(hass, 1, STORAGE_KEY))
        self.lock = asyncio.Lock()
        self.listeners: set[Callable[[], None]] = set()
        self.outage_started: float | None = None
        self.pairing_task: asyncio.Task | None = None
        self.pairing_until: datetime | None = None

    @callback
    def forget_state(self) -> None:
        """Remote presses that nobody heard could have changed the panel."""
        self.state.is_on = None
        self.state.effect = None

    @callback
    def notify(self) -> None:
        for listener in tuple(self.listeners):
            listener()

    @callback
    def receive(self, event: Event) -> None:
        raw = event.data.get("raw")
        if not isinstance(raw, str) or len(raw) > 124:
            return
        try:
            advertisement = bytes.fromhex(raw)
        except ValueError:
            return
        for message in self.codec.decode(advertisement):
            command = self.remote.accept(message)
            if command is not None:
                self.state.apply(command)
                self.notify()

    async def _async_transmit_locked(
        self, payload_builder: Callable[[int], bytes], repeat: int = 3
    ) -> None:
        """Reserve before transmitting; caller holds the shared command lock."""
        try:
            seq = await self.sequence.async_next()
            payload = payload_builder(0x80 | (seq & 0x7F))
            raw = self.codec.encode(payload, seq).hex()
            await self.hass.services.async_call(
                "esphome",
                self.service,
                {
                    "raw": raw,
                    "duration": 100,
                    "repeat": repeat,
                    "ignored_advs": [raw],
                    "ignored_duration": 20000,
                },
                blocking=True,
            )
        except (ValueError, OSError) as err:
            raise HomeAssistantError(f"Cannot send Skylight command: {err}") from err

    async def async_send_locked(self, command: str) -> None:
        """Caller holds lock, including power decision. Never retry a toggle."""
        await self._async_transmit_locked(lambda transaction: command_payload(command, transaction))
        self.state.apply(command)
        self.notify()
        # The API action enqueues packets; leave time for its three advertising bursts.
        await asyncio.sleep(0.45)

    async def async_send(self, command: str) -> None:
        async with self.lock:
            await self.async_send_locked(command)

    async def async_dim(self, direction: str, hold: float = 0) -> None:
        """One step for a tap, or the remote's hold command repeated for `hold` seconds."""
        command = f"dim_{direction}"
        if not hold:
            await self.async_send(command)
            return
        for _ in range(max(1, round(hold / HOLD_INTERVAL))):
            async with self.lock:
                await self._async_transmit_locked(
                    lambda transaction: command_payload(command + "_hold", transaction)
                )
                self.state.apply(command)
                self.notify()
            await asyncio.sleep(HOLD_INTERVAL)

    async def async_pair(self) -> None:
        """Send the pairing request for 10 seconds in the background. Returns at once."""
        self._start_pairing(pairing_payload, "pairing", PAIRING_BURST)

    async def async_unpair_all(self) -> None:
        """Ask the panel to forget every paired sender, this one included."""
        self._start_pairing(unpair_all_payload, "unpair all", PAIRING_BURST)

    @callback
    def _start_pairing(
        self, payload_builder: Callable[[int], bytes], label: str, duration: float
    ) -> None:
        # The panel listens only for a short time after its power returns, so the
        # user selects Pair as soon as the panel is back on.
        self.stop_pairing()
        self.pairing_until = dt_util.utcnow() + timedelta(seconds=duration)
        self.state.is_on = None
        self.state.effect = None
        self.state.last_command = label
        self.notify()
        self.pairing_task = self.hass.async_create_background_task(
            self._async_repeat(payload_builder, round(duration * PAIRING_RATE)), f"Skylight {label}"
        )

    async def _async_repeat(self, payload_builder: Callable[[int], bytes], count: int) -> None:
        try:
            for _ in range(count):
                try:
                    # Take the lock per request, so other commands still get through.
                    async with self.lock:
                        await self._async_transmit_locked(payload_builder, repeat=1)
                except HomeAssistantError:
                    _LOGGER.debug("Skylight pairing request not sent", exc_info=True)
                await asyncio.sleep(1 / PAIRING_RATE)
        finally:
            # Neither the requests nor their end confirm pairing or power.
            self.pairing_until = None
            self.state.is_on = None
            self.state.effect = None
            self.notify()

    @callback
    def stop_pairing(self) -> None:
        if self.pairing_task and not self.pairing_task.done():
            self.pairing_task.cancel()

    async def async_skip_sequence(self) -> int:
        """Recover from a lost sequence Store without changing the sender address."""
        async with self.lock:
            start = await self.sequence.async_skip()
        _LOGGER.warning("Skylight mesh sequence skipped forward to %s", start)
        return start

    async def async_power(self, on: bool, effect: str | None = None) -> None:
        async with self.lock:
            if on and effect is not None:
                # A mode command turns the panel on in that mode, whatever its power.
                await self.async_send_locked(effect)
                return
            if self.state.is_on is None:
                raise HomeAssistantError(
                    "Skylight power is unknown. Check the physical light, then call "
                    f"{DOMAIN}.set_assumed_power with its current power state, "
                    "or turn it on with an effect."
                )
            if self.state.is_on != on:
                await self.async_send_locked("toggle")

    async def async_setup_receiver(self) -> None:
        """Initialize filtering after HA reconnects to the proxy."""
        service = self.service.removesuffix("adv_svc_v1") + "setup_svc_v0"
        if self.hass.services.has_service("esphome", service):
            try:
                await self.hass.services.async_call(
                    "esphome",
                    service,
                    {"ignored_duration": 20000, "ignored_cids": [], "ignored_macs": []},
                    blocking=True,
                )
            except HomeAssistantError:
                _LOGGER.warning("Could not initialize Skylight remote reception", exc_info=True)

    @callback
    def async_subscribe(self) -> Callable[[], None]:
        return self.hass.bus.async_listen(RECEIVE_EVENT, self.receive)


type SkylightConfigEntry = ConfigEntry[SkylightController]
