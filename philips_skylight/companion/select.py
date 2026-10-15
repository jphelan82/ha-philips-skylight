"""Record the physically observed scene using a standard HA select entity."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EFFECTS
from .controller import SkylightConfigEntry
from .entity import SkylightEntity

UNKNOWN_SCENE = "Unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SkylightRecordedScene(entry.runtime_data, entry)])


class SkylightRecordedScene(SkylightEntity, SelectEntity):
    _attr_name = "Recorded scene"
    _attr_unique_id = "factory_mesh_7ffe_recorded_scene"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:eye-check-outline"
    _attr_options = [UNKNOWN_SCENE, *EFFECTS]

    @property
    def available(self) -> bool:
        # Records only and never transmits, so it works while the proxy is offline.
        return True

    @property
    def current_option(self):
        return self.controller.state.effect or UNKNOWN_SCENE

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ServiceValidationError(f"Unknown Skylight scene: {option}")
        async with self.controller.lock:
            self.controller.state.effect = None if option == UNKNOWN_SCENE else option
            self.controller.notify()
