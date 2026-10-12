"""Light entity with explicit assumed power and captured scene effects."""

import voluptuous as vol
from homeassistant.components.light import ATTR_EFFECT, ColorMode, LightEntity, LightEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform

from .const import DOMAIN, EFFECTS, VERSION
from .entity import SkylightEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SkylightLight(hass.data[DOMAIN][entry.entry_id], entry)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_assumed_power", {vol.Required("is_on"): cv.boolean}, "async_set_assumed_power"
    )
    platform.async_register_entity_service(
        "pair_transmitter", {vol.Required("confirm"): cv.boolean}, "async_pair_transmitter"
    )


class SkylightLight(SkylightEntity, LightEntity):
    _attr_name = None
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
        }

    async def async_set_assumed_power(self, is_on: bool) -> None:
        async with self.controller.lock:
            self.controller.state.is_on = is_on
            self.controller.notify()

    async def async_pair_transmitter(self, confirm: bool) -> None:
        if not confirm:
            raise HomeAssistantError(
                "Pairing may replace the working remote. Set confirm to true only "
                "when ready to test after cycling the panel's mains power."
            )
        await self.controller.async_pair()

    async def async_turn_on(self, **kwargs) -> None:
        effect = kwargs.get(ATTR_EFFECT)
        if effect is not None and effect not in EFFECTS:
            raise HomeAssistantError(f"Unknown Skylight effect: {effect}")
        await self.controller.async_power(True, effect)

    async def async_turn_off(self, **kwargs) -> None:
        await self.controller.async_power(False)

    async def async_toggle(self, **kwargs) -> None:
        await self.controller.async_send("toggle")
