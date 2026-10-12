"""Reserve mesh sequence ranges durably before any packets can be sent."""

import asyncio
from typing import Any

from .const import SEQUENCE_BLOCK


class SequenceAllocator:
    """Store is a Home Assistant Store, or any async_load/async_save implementation."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self._next = 0
        self._limit = 0
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        saved = await self.store.async_load()
        if saved is None:
            high_watermark = 0
        elif (
            not isinstance(saved, dict)
            or type(saved.get("high_watermark")) is not int
            or not 0 <= saved["high_watermark"] <= 0x1000000
        ):
            raise ValueError("Invalid sequence storage; refusing to reuse mesh sequence numbers")
        else:
            high_watermark = saved["high_watermark"]
        self._next = self._limit = high_watermark

    async def async_next(self) -> int:
        async with self._lock:
            if self._next >= 0x1000000:
                raise ValueError(
                    "Mesh sequence exhausted; use a new sender address and IV strategy"
                )
            if self._next == self._limit:
                limit = min(self._next + SEQUENCE_BLOCK, 0x1000000)
                # Do not expose this range until the write completes successfully.
                await self.store.async_save({"high_watermark": limit})
                self._limit = limit
            value = self._next
            self._next += 1
            return value
