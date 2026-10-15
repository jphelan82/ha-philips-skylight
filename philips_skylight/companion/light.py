"""Light entity with explicit assumed power and captured scene effects."""

from homeassistant.components.light import ATTR_EFFECT, ColorMode, LightEntity, LightEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EFFECTS, VERSION
from .controller import SkylightConfigEntry
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    # The Skylight actions are domain actions in services.py, not entity actions.
    async_add_entities([SkylightLight(entry.runtime_data, entry)])


class SkylightLight(SkylightEntity, LightEntity):
    _attr_name = None
    _attr_icon = "mdi:wall-sconce-flat"
    _attr_unique_id = "factory_mesh_7ffe_light"
    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(EFFECTS)

    @property
    def is_on(self):
        return self.controller.state.is_on

    @property
    def effect(self):
        return self.controller.state.effect

    @property
    def extra_state_attributes(self):
        return {
            "integration_version": VERSION,
            "state_feedback": "assumed; panel does not report state",
            "last_command": self.controller.state.last_command,
            "power_synchronized": self.is_on is not None,
            "assumed_effect": self.controller.state.effect,
            "pairing_until": (
                self.controller.pairing_until.isoformat() if self.controller.pairing_until else None
            ),
        }

    async def async_turn_on(self, **kwargs) -> None:
        effect = kwargs.get(ATTR_EFFECT)
        if effect is not None and effect not in EFFECTS:
            raise ServiceValidationError(f"Unknown Skylight effect: {effect}")
        await self.controller.async_power(True, effect)

    async def async_turn_off(self, **kwargs) -> None:
        await self.controller.async_power(False)

    async def async_toggle(self, **kwargs) -> None:
        if kwargs.get(ATTR_EFFECT) is not None:
            # An effect sets that mode and turns the panel on. It never turns it off.
            await self.async_turn_on(**kwargs)
            return
        await self.controller.async_send("toggle")
