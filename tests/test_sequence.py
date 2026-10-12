"""Crash/restart, failed writes, concurrency, and exhaustion invariants."""

import asyncio
from copy import deepcopy

import pytest

from custom_components.philips_skylight.sequence import SequenceAllocator


class MemoryStore:
    def __init__(self, saved=None):
        self.saved = saved
        self.fail = False

    async def async_load(self):
        return deepcopy(self.saved)

    async def async_save(self, saved):
        if self.fail:
            raise OSError("disk full")
        self.saved = deepcopy(saved)


async def test_restart_skips_all_previously_reserved_sequences():
    store = MemoryStore()
    allocator = SequenceAllocator(store)
    await allocator.async_load()
    assert await allocator.async_next() == 0
    assert store.saved == {"high_watermark": 256}
    restarted = SequenceAllocator(store)
    await restarted.async_load()
    assert await restarted.async_next() == 256
    assert store.saved == {"high_watermark": 512}


async def test_failed_reservation_does_not_expose_sequence():
    store = MemoryStore()
    allocator = SequenceAllocator(store)
    await allocator.async_load()
    store.fail = True
    with pytest.raises(OSError):
        await allocator.async_next()
    store.fail = False
    assert await allocator.async_next() == 0
    assert store.saved["high_watermark"] == 256


async def test_concurrent_requests_are_unique_across_reservation_boundaries():
    store = MemoryStore()
    allocator = SequenceAllocator(store)
    await allocator.async_load()
    sequences = await asyncio.gather(*(allocator.async_next() for _ in range(600)))
    assert sequences == list(range(600))
    assert store.saved["high_watermark"] == 768


@pytest.mark.parametrize("saved", [{}, [], {"high_watermark": -1}, {"high_watermark": True}])
async def test_corrupt_storage_fails_closed(saved):
    with pytest.raises(ValueError):
        await SequenceAllocator(MemoryStore(saved)).async_load()


async def test_sequence_never_wraps():
    allocator = SequenceAllocator(MemoryStore({"high_watermark": 0xFFFFFF}))
    await allocator.async_load()
    assert await allocator.async_next() == 0xFFFFFF
    with pytest.raises(ValueError, match="exhausted"):
        await allocator.async_next()
