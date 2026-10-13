"""A real HA service bus without network connections or a running server."""

import sys
from pathlib import Path

import pytest
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    await instance.config_entries.async_initialize()
    yield instance
    await instance.async_block_till_done()
    await instance.async_stop(force=True)
