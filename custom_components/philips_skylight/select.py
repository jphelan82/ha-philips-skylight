"""Record the physically observed scene using a standard HA select entity."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, EFFECTS
from .entity import SkylightEntity

UNKNOWN_SCENE = "Unknown"


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SkylightRecordedScene(hass.data[DOMAIN][entry.entry_id], entry)])


class SkylightRecordedScene(SkylightEntity, SelectEntity):
    _attr_name = "Recorded scene"
    _attr_unique_id = "factory_mesh_7ffe_recorded_scene"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:eye-check-outline"
    _attr_options = [UNKNOWN_SCENE, *EFFECTS]

    @property
    def current_option(self):
        return self.controller.state.effect or UNKNOWN_SCENE

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise HomeAssistantError(f"Unknown Skylight scene: {option}")
        async with self.controller.lock:
            self.controller.state.effect = None if option == UNKNOWN_SCENE else option
            self.controller.notify()
