"""Serialize commands and forward authenticated packets to an ESPHome proxy."""

import asyncio
import contextlib
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
    EFFECTS,
    HOLD_INTERVAL,
    OUTAGE_GRACE,
    PAIRING_BURST,
    PAIRING_RATE,
    RECEIVE_EVENT,
    SOURCE,
    STATUS_DELAY,
    STATUS_INTERVAL,
    STATUS_WINDOW,
    STORAGE_KEY,
)
from .model import AssumedState, RemoteTracker
from .protocol import (
    ONOFF_GET,
    MeshCodec,
    command_payload,
    onoff_status,
    pairing_payload,
    unpair_all_payload,
)
from .sequence import SequenceAllocator

_LOGGER = logging.getLogger(__name__)
OFFLINE = ("unavailable", "unknown")


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
        # Counts sends and remote presses that can change the power. A status
        # answer counts only if this count did not change after its request.
        self.power_changes = 0
        self.status_request: tuple[int, asyncio.Future[bool]] | None = None
        self.status_due = monotonic() + STATUS_DELAY
        self.status_wake = asyncio.Event()

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
            if message.destination == SOURCE:
                self._receive_status(message.source, message.payload)
                continue
            command = self.remote.accept(message)
            if command is not None:
                if command == "toggle" or command in EFFECTS:
                    self.power_changes += 1
                self.state.apply(command)
                self.notify()
                if command == "toggle":
                    self.request_status(STATUS_DELAY)

    @callback
    def _receive_status(self, source: int, payload: bytes) -> None:
        """Apply the panel's answer to the open Generic OnOff Get, if any."""
        power = onoff_status(payload)
        request = self.status_request
        if power is None or request is None or not 1 <= source <= 0x7FFF or source == SOURCE:
            return
        changes, answer = request
        if answer.done():
            return
        if changes != self.power_changes:
            # The answer can describe the power from before the newer command.
            answer.set_result(False)
            return
        _LOGGER.debug("Skylight panel 0x%04X reports power %s", source, "on" if power else "off")
        answer.set_result(True)
        if self.stopped or self.pairing_until:
            return
        self.state.is_on = power
        self.notify()

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
        self.power_changes += 1
        await self._async_transmit_locked(lambda transaction: command_payload(command, transaction))
        self.state.apply(command)
        self.notify()
        if command == "toggle":
            self.request_status(STATUS_DELAY)
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
        self.power_changes += 1
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
                self.request_status(STATUS_DELAY)

    @callback
    def stop_pairing(self) -> None:
        if self.pairing_task and not self.pairing_task.done():
            self.pairing_task.cancel()

    async def async_stop(self) -> None:
        """Unload: stop every background send and send nothing more."""
        self.stopped = True
        tasks = tuple(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks)

    async def async_set_assumed_power(self, is_on: bool) -> None:
        """Record the observed power without sending a command."""
        async with self.lock:
            self.state.is_on = is_on
            self.notify()

    async def async_skip_sequence(self) -> int:
        """Recover from a lost sequence Store without changing the sender address."""
        async with self.lock:
            start = await self.sequence.async_skip()
        _LOGGER.warning("Skylight mesh sequence skipped forward to %s", start)
        return start

    async def async_power(self, on: bool, effect: str | None = None) -> None:
        if (
            self.state.is_on is None
            and effect is None
            and not self.pairing_until
            and self.transmitter_ready
        ):
            # Ask the panel first. If it does not answer, the error below explains.
            with contextlib.suppress(HomeAssistantError):
                await self.async_refresh_power()
        async with self.lock:
            if on and effect is not None:
                # A mode command turns the panel on in that mode, whatever its power.
                await self.async_send_locked(effect)
                return
            if self.state.is_on is None:
                raise HomeAssistantError(
                    "Skylight power is unknown, and the panel did not report it. "
                    "Check the physical light, then call "
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

    async def async_refresh_power(self) -> bool:
        """Ask the panel for its power. True if it answered and the power is now known."""
        answer: asyncio.Future[bool] = self.hass.loop.create_future()
        async with self.lock:
            if not self.transmitter_ready:
                raise HomeAssistantError(
                    "Cannot reach the Skylight proxy. Check that the proxy is online, "
                    "then try again."
                )
            # Open the request before sending: the answer can arrive during the send.
            self.status_request = (self.power_changes, answer)
            try:
                await self._async_transmit_locked(lambda transaction: ONOFF_GET)
            except BaseException:
                self.status_request = None
                raise
        try:
            async with asyncio.timeout(STATUS_WINDOW):
                return await answer
        except TimeoutError:
            return False
        finally:
            if self.status_request is not None and self.status_request[1] is answer:
                self.status_request = None

    @callback
    def request_status(self, delay: float) -> None:
        """Ask for the power after `delay` seconds. This replaces an earlier time."""
        self.status_due = monotonic() + delay
        self.status_wake.set()

    @callback
    def async_start_status(self) -> None:
        """Ask for the power soon after setup, then every STATUS_INTERVAL seconds."""
        self._track(
            self.hass.async_create_background_task(
                self._async_status_loop(), "Skylight power status"
            )
        )

    async def _async_status_loop(self) -> None:
        while not self.stopped:
            self.status_wake.clear()
            wait = self.status_due - monotonic()
            if wait > 0:
                # A toggle or reconnect wakes the loop with a new time.
                with contextlib.suppress(TimeoutError):
                    async with asyncio.timeout(wait):
                        await self.status_wake.wait()
                continue
            self.status_due = monotonic() + STATUS_INTERVAL
            if self.pairing_until or not self.transmitter_ready:
                continue
            try:
                if not await self.async_refresh_power():
                    _LOGGER.debug("Skylight panel did not report its power")
            except HomeAssistantError as err:
                _LOGGER.debug("Skylight power request not sent: %s", err)

    @callback
    def async_subscribe(self) -> Callable[[], None]:
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
            self.request_status(STATUS_DELAY)
        self.notify()


type SkylightConfigEntry = ConfigEntry[SkylightController]
