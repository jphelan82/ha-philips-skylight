"""Serialize commands and forward authenticated packets to an ESPHome proxy."""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from time import monotonic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PROXY_ENTITY,
    CONF_TRANSMIT_SERVICE,
    DOMAIN,
    HOLD_INTERVAL,
    OUTAGE_GRACE,
    PAIRING_BURST,
    PAIRING_RATE,
    RECEIVE_EVENT,
    SOURCE,
    STORAGE_KEY,
)
from .model import AssumedState, RemoteTracker
from .protocol import MeshCodec, command_payload, pairing_payload, unpair_all_payload
from .sequence import SequenceAllocator

_LOGGER = logging.getLogger(__name__)
OFFLINE = ("unavailable", "unknown")

# Enable after validating manual GET against deliberately incorrect assumed power.
ENABLE_BACKGROUND_QUERIES = True
STATUS_SOURCE = 0x3CC2
POLL_INTERVAL_SECONDS = 30
VERIFY_AFTER_TOGGLE_SECONDS = 5
STATUS_RESPONSE_WINDOW_SECONDS = 3


class SkylightController:
    def __init__(self, hass: HomeAssistant, data: dict) -> None:
        self.hass = hass
        self.service = data[CONF_TRANSMIT_SERVICE]
        self.proxy_entity = data[CONF_PROXY_ENTITY]
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
        # Counts bursts, so a cancelled burst cannot clear the state of the next one.
        self.pairing_burst = 0
        # Background sends and setup calls that unload cancels.
        self.tasks: set[asyncio.Task] = set()
        self.stopped = False
        self._poll_task: asyncio.Task | None = None
        self._verification_task: asyncio.Task | None = None
        self._status_response_deadline = 0.0
        self._next_status_query_at = 0.0
        self._verify_not_before = 0.0
        self._last_status_sequence = -1
        self._last_status_query_at = -1.0
        self._command_generation = 0

    @property
    def transmitter_ready(self) -> bool:
        """The proxy is online and its advertising action exists."""
        proxy = self.hass.states.get(self.proxy_entity)
        return (
            proxy is not None
            and proxy.state not in OFFLINE
            and self.hass.services.has_service("esphome", self.service)
        )

    @callback
    def _track(self, task: asyncio.Task) -> asyncio.Task:
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

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
            if (
                message.source == STATUS_SOURCE
                and message.destination == SOURCE
                and message.payload in (b"\x82\x04\x00", b"\x82\x04\x01")
            ):
                # Track even unsolicited/late replies so they cannot be replayed
                # inside a later response window. The codec uses a fixed IV index.
                if message.sequence <= self._last_status_sequence:
                    continue
                self._last_status_sequence = message.sequence
                now = monotonic()
                if not self.stopped and now < self._status_response_deadline:
                    self._status_response_deadline = 0.0
                    self.state.is_on = message.payload[-1] == 1
                    self.notify()
                    _LOGGER.debug("Skylight confirmed power: %s", self.state.is_on)
                continue
            command = self.remote.accept(message)
            if command is not None:
                self._invalidate_pending_status()
                self.state.apply(command)
                self.notify()
                if command == "toggle":
                    self._schedule_toggle_verification()

    async def _async_transmit_locked(
        self, payload_builder: Callable[[int], bytes], repeat: int = 3
    ) -> None:
        """Reserve before transmitting; caller holds the shared command lock."""
        if self.stopped:
            # A reloaded entry has a new controller that reserves from the same Store.
            raise HomeAssistantError("The Skylight integration is unloaded")
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
        self._invalidate_pending_status()
        await self._async_transmit_locked(lambda transaction: command_payload(command, transaction))
        self._invalidate_pending_status()
        self.state.apply(command)
        self.notify()
        if command == "toggle":
            self._schedule_toggle_verification()
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
        # Run the hold in its own task, so unload can stop it.
        task = self._track(
            self.hass.async_create_task(self._async_hold(command, hold), f"Skylight {command} hold")
        )
        try:
            await task
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
            raise HomeAssistantError("The Skylight integration unloaded during the hold") from None

    async def _async_hold(self, command: str, hold: float) -> None:
        for _ in range(max(1, round(hold / HOLD_INTERVAL))):
            async with self.lock:
                self._invalidate_pending_status()
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
        if not self.transmitter_ready:
            raise HomeAssistantError(
                "Cannot reach the Skylight proxy. Check that the proxy is online, then try again."
            )
        self.stop_pairing()
        self._invalidate_pending_status()
        self.pairing_burst += 1
        self.pairing_until = dt_util.utcnow() + timedelta(seconds=duration)
        self.state.is_on = None
        self.state.effect = None
        self.state.last_command = label
        self.notify()
        self.pairing_task = self._track(
            self.hass.async_create_background_task(
                self._async_repeat(
                    payload_builder, round(duration * PAIRING_RATE), label, self.pairing_burst
                ),
                f"Skylight {label}",
            )
        )

    async def _async_repeat(
        self, payload_builder: Callable[[int], bytes], count: int, label: str, burst: int
    ) -> None:
        failed = 0
        try:
            for _ in range(count):
                try:
                    # Take the lock per request, so other commands still get through.
                    async with self.lock:
                        await self._async_transmit_locked(payload_builder, repeat=1)
                except HomeAssistantError as err:
                    failed += 1
                    if failed == 1:
                        _LOGGER.warning("Skylight %s request not sent: %s", label, err)
                    else:
                        _LOGGER.debug("Skylight %s request not sent", label, exc_info=True)
                await asyncio.sleep(1 / PAIRING_RATE)
        finally:
            # A newer burst owns pairing_until and the state now.
            if burst == self.pairing_burst:
                # Neither the requests nor their end confirm pairing or power.
                self.pairing_until = None
                self.state.is_on = None
                self.state.effect = None
                self.notify()

    @callback
    def stop_pairing(self) -> None:
        if self.pairing_task and not self.pairing_task.done():
            self.pairing_task.cancel()

    async def async_stop(self) -> None:
        """Unload: stop every background send and send nothing more."""
        self.stopped = True
        self._status_response_deadline = 0.0
        tasks = tuple(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks)

    async def async_set_assumed_power(self, is_on: bool) -> None:
        """Record the observed power without sending a command."""
        async with self.lock:
            self._status_response_deadline = 0.0
            self.state.is_on = is_on
            self.notify()

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

    def _invalidate_pending_status(self) -> None:
        """Invalidate before yielding to any power-changing transmission."""
        self._status_response_deadline = 0.0
        self._verify_not_before = monotonic() + VERIFY_AFTER_TOGGLE_SECONDS
        self._command_generation += 1

    @callback
    def _schedule_toggle_verification(self) -> None:
        if self.stopped or not ENABLE_BACKGROUND_QUERIES:
            return
        # One worker follows the latest deadline; never cancel an in-flight send.
        if self._verification_task is None or self._verification_task.done():
            self._verification_task = self._track(
                self.hass.async_create_background_task(
                    self._async_verify_after_toggle(), "Skylight verify toggle"
                )
            )

    async def _async_verify_after_toggle(self) -> None:
        while not self.stopped:
            await asyncio.sleep(max(0, self._verify_not_before - monotonic()))
            if self._last_status_query_at >= self._verify_not_before:
                return
            generation = self._command_generation
            try:
                if await self.async_test_onoff_get():
                    if generation == self._command_generation:
                        return
                    continue
                # A periodic/manual query already covers this verification.
                if self._status_response_deadline > monotonic():
                    return
                await asyncio.sleep(max(0.01, self._next_status_query_at - monotonic()))
            except HomeAssistantError as err:
                _LOGGER.debug("Skylight toggle verification skipped: %s", err)
                return

    async def _async_poll_loop(self) -> None:
        while not self.stopped:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            try:
                await self.async_test_onoff_get()
            except HomeAssistantError as err:
                _LOGGER.debug("Skylight periodic query skipped: %s", err)

    async def async_test_onoff_get(self) -> bool:
        """Send one GET; return False when a recent command/query defers it."""
        async with self.lock:
            if self.stopped or not self.transmitter_ready:
                raise HomeAssistantError("Skylight transmitter is unavailable")
            now = monotonic()
            if now < max(self._verify_not_before, self._next_status_query_at):
                _LOGGER.debug("Skylight GET deferred: recent command or query")
                return False
            if self._status_response_deadline:
                _LOGGER.debug("Skylight previous GET expired without confirmation")
            # Arm before the service call: receive() can run while it awaits.
            self._status_response_deadline = now + STATUS_RESPONSE_WINDOW_SECONDS
            self._next_status_query_at = self._status_response_deadline
            try:
                await self._async_transmit_locked(lambda transaction: b"\x82\x01", repeat=1)
            except BaseException:
                self._status_response_deadline = 0.0
                raise
            _LOGGER.debug("Skylight Generic OnOff GET sent")
            self._last_status_query_at = now
            return True

    @callback
    def async_subscribe(self) -> Callable[[], None]:
        if ENABLE_BACKGROUND_QUERIES and (self._poll_task is None or self._poll_task.done()):
            self._poll_task = self._track(
                self.hass.async_create_background_task(
                    self._async_poll_loop(), "Skylight power polling"
                )
            )
        return self.hass.bus.async_listen(RECEIVE_EVENT, self.receive)

    @callback
    def async_track_proxy(self) -> Callable[[], None]:
        """Follow the proxy here, not in an entity that the user can disable."""
        return async_track_state_change_event(self.hass, [self.proxy_entity], self._proxy_changed)

    @callback
    def _proxy_changed(self, event: Event) -> None:
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        offline = new is None or new.state in OFFLINE
        was_offline = old is None or old.state in OFFLINE
        if new is None:
            # The proxy sensor was removed, not just disconnected.
            self.outage_started = None
            self.forget_state()
        elif offline and not was_offline:
            self.outage_started = monotonic()
        elif not offline and was_offline:
            started = self.outage_started
            self.outage_started = None
            # The proxy drops for a fraction of a second now and then. Keep the
            # recorded state then, but not after an outage long enough to miss presses.
            if started is None or monotonic() - started > OUTAGE_GRACE:
                self.forget_state()
            self._track(
                self.hass.async_create_task(self.async_setup_receiver(), "Skylight receiver setup")
            )
        self.notify()


type SkylightConfigEntry = ConfigEntry[SkylightController]
