"""Known relative dim commands and direct scene selection."""

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN, EFFECTS
from .entity import SkylightEntity


async def async_setup_entry(hass, entry, async_add_entities):
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SkylightButton(controller, entry, command, name)
        for command, name in (
            ("dim_down", "Dim down"),
            ("dim_up", "Dim up"),
            *((effect, effect) for effect in EFFECTS),
        )
    )


class SkylightButton(SkylightEntity, ButtonEntity):
    def __init__(self, controller, entry, command: str, name: str):
        super().__init__(controller, entry)
        self.command = command
        self._attr_name = name
        self._attr_unique_id = f"factory_mesh_7ffe_{command.lower().replace(' ', '_')}"
        self._attr_icon = "mdi:brightness-6" if command.startswith("dim") else "mdi:palette"

    async def async_press(self) -> None:
        await self.controller.async_send(self.command)
