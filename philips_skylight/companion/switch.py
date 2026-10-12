"""Dashboard view mode; never transmit a command to the physical panel."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import SkylightEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SkylightStateCorrection(hass.data[DOMAIN][entry.entry_id], entry)])


class SkylightStateCorrection(SkylightEntity, SwitchEntity):
    _attr_name = "State correction"
    _attr_unique_id = "factory_mesh_7ffe_state_correction"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:pencil-outline"

    @property
    def available(self):
        # Allow leaving correction mode even while the BLE proxy is offline.
        return True

    @property
    def is_on(self):
        return self.controller.state_correction

    async def async_turn_on(self, **kwargs) -> None:
        self.controller.state_correction = True
        self.controller.notify()

    async def async_turn_off(self, **kwargs) -> None:
        self.controller.state_correction = False
        self.controller.notify()
