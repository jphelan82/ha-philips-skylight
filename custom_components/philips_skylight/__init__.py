"""Philips Skylight control through raw BLE mesh advertising."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import SkylightConfigEntry, SkylightController

PLATFORMS = [Platform.LIGHT, Platform.BUTTON, Platform.SELECT, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    controller = SkylightController(hass, entry.data)
    await controller.sequence.async_load()
    entry.runtime_data = controller
    entry.async_on_unload(controller.async_subscribe())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_setup_receiver()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
