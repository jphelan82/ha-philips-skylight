"""Light entity with explicit assumed power and captured scene effects."""

import voluptuous as vol
from homeassistant.components.light import ATTR_EFFECT, ColorMode, LightEntity, LightEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EFFECTS, PAIRING_WINDOW, VERSION
from .controller import SkylightConfigEntry
from .entity import SkylightEntity

PAIR_CONFIRM = (
    "Set confirm to true to start pairing. Then switch the panel's power off and on "
    "at its light switch or breaker before the window ends."
)
UNPAIR_CONFIRM = (
    "Unpairing removes every remote, the original one included, and this "
    "transmitter. Set confirm to true only if you will pair them all again."
)
WINDOW = vol.All(vol.Coerce(float), vol.Range(min=5, max=300))
SKIP_CONFIRM = (
    "Skip the sequence only when the panel ignores this transmitter after "
    "Home Assistant was rebuilt or restored from an older backup."
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SkylightLight(entry.runtime_data, entry)])
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_assumed_power", {vol.Required("is_on"): cv.boolean}, "async_set_assumed_power"
    )
    # Reject a missing confirmation in the schema, so the REST API answers 400.
    platform.async_register_entity_service(
        "pair_transmitter",
        {
            vol.Required("confirm"): vol.All(cv.boolean, vol.IsTrue(PAIR_CONFIRM)),
            vol.Optional("duration", default=PAIRING_WINDOW): WINDOW,
        },
        "async_pair_transmitter",
    )
    platform.async_register_entity_service(
        "unpair_all_remotes",
        {
            vol.Required("confirm"): vol.All(cv.boolean, vol.IsTrue(UNPAIR_CONFIRM)),
            vol.Optional("duration", default=PAIRING_WINDOW): WINDOW,
        },
        "async_unpair_all_remotes",
    )
    platform.async_register_entity_service("stop_pairing", None, "async_stop_pairing")
    platform.async_register_entity_service(
        "dim",
        {
            vol.Required("direction"): vol.In(["down", "up"]),
            vol.Optional("hold", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        },
        "async_dim",
    )
    platform.async_register_entity_service(
        "skip_sequence",
        {vol.Required("confirm"): vol.All(cv.boolean, vol.IsTrue(SKIP_CONFIRM))},
        "async_skip_sequence",
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
            "assumed_effect": self.controller.state.effect,
            "pairing_until": (
                self.controller.pairing_until.isoformat() if self.controller.pairing_until else None
            ),
        }

    async def async_set_assumed_power(self, is_on: bool) -> None:
        async with self.controller.lock:
            self.controller.state.is_on = is_on
            self.controller.notify()

    async def async_pair_transmitter(
        self, confirm: bool, duration: float = PAIRING_WINDOW
    ) -> None:
        if not confirm:
            raise ServiceValidationError(PAIR_CONFIRM)
        await self.controller.async_pair(duration)

    async def async_dim(self, direction: str, hold: float = 0) -> None:
        await self.controller.async_dim(direction, hold)

    async def async_stop_pairing(self) -> None:
        self.controller.stop_pairing()

    async def async_unpair_all_remotes(
        self, confirm: bool, duration: float = PAIRING_WINDOW
    ) -> None:
        if not confirm:
            raise ServiceValidationError(UNPAIR_CONFIRM)
        await self.controller.async_unpair_all(duration)

    async def async_skip_sequence(self, confirm: bool) -> None:
        if not confirm:
            raise ServiceValidationError(SKIP_CONFIRM)
        await self.controller.async_skip_sequence()

    async def async_turn_on(self, **kwargs) -> None:
        effect = kwargs.get(ATTR_EFFECT)
        if effect is not None and effect not in EFFECTS:
            raise ServiceValidationError(f"Unknown Skylight effect: {effect}")
        await self.controller.async_power(True, effect)

    async def async_turn_off(self, **kwargs) -> None:
        await self.controller.async_power(False)

    async def async_toggle(self, **kwargs) -> None:
        await self.controller.async_send("toggle")
