"""Philips Skylight control through raw BLE mesh advertising."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .controller import SkylightController

PLATFORMS = [Platform.LIGHT, Platform.BUTTON, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = SkylightController(hass, entry.data)
    await controller.sequence.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    entry.async_on_unload(controller.async_subscribe())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_setup_receiver()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
