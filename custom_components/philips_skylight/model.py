"""Assumed light state and duplicate filtering, independent of Home Assistant."""

from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic

from .const import DESTINATION, EFFECTS, SOURCE
from .protocol import MeshMessage, identify_command


@dataclass
class AssumedState:
    is_on: bool | None = None
    effect: str | None = None
    last_command: str | None = None

    def apply(self, command: str) -> None:
        if command == "toggle" and self.is_on is not None:
            self.is_on = not self.is_on
        if command in EFFECTS:
            self.effect = command
        self.last_command = command


@dataclass
class RemoteTracker:
    # Relays change TTL and encryption, so compare decrypted identity, not raw bytes.
    _seen: OrderedDict = field(default_factory=OrderedDict)
    _recent_payloads: OrderedDict = field(default_factory=OrderedDict)

    def accept(self, message: MeshMessage, now: float | None = None) -> str | None:
        # Compatible remotes need not use the captured remote's 0x7FFF address.
        # Own packets can return through panel relays; never apply them twice.
        if (
            not 1 <= message.source <= 0x7FFF
            or message.source == SOURCE
            or message.destination != DESTINATION
        ):
            return None
        command = identify_command(message.payload)
        if command is None:
            return None
        now = monotonic() if now is None else now
        identity = (message.source, message.sequence)
        if identity in self._seen:
            return None
        self._seen[identity] = None
        if len(self._seen) > 512:
            self._seen.popitem(last=False)
        # Same transaction may be retransmitted with a different mesh sequence.
        transaction = (message.source, message.payload)
        last_time = self._recent_payloads.get(transaction)
        if last_time is not None and now - last_time < 0.4:
            return None
        self._recent_payloads[transaction] = now
        self._recent_payloads.move_to_end(transaction)
        if len(self._recent_payloads) > 512:
            self._recent_payloads.popitem(last=False)
        return command
