"""Dashboard view mode; never transmit a command to the physical panel."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controller import SkylightConfigEntry
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SkylightStateCorrection(entry.runtime_data, entry)])


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
