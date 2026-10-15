"""Philips Skylight control through raw BLE mesh advertising."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .controller import SkylightConfigEntry, SkylightController
from .services import async_setup_services

PLATFORMS = [Platform.LIGHT, Platform.BUTTON, Platform.SELECT, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    controller = SkylightController(hass, entry.data)
    await controller.sequence.async_load()
    entry.runtime_data = controller
    entry.async_on_unload(controller.async_subscribe())
    entry.async_on_unload(controller.async_track_proxy())
    # Unload stops hold loops and pairing bursts, so a reloaded entry's new
    # controller is the only one that reserves sequence numbers.
    entry.async_on_unload(controller.async_stop)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_setup_receiver()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkylightConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
