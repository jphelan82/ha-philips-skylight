"""Known relative dim commands and direct scene selection."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EFFECTS
from .controller import SkylightConfigEntry, SkylightController
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    async_add_entities(
        SkylightButton(controller, entry, command, name)
        for command, name in (
            ("dim_down", "Dim down"),
            ("dim_up", "Dim up"),
            *((effect, effect) for effect in EFFECTS),
        )
    )
    async_add_entities(
        SkylightPowerSyncButton(controller, entry, is_on) for is_on in (True, False)
    )


class SkylightButton(SkylightEntity, ButtonEntity):
    def __init__(
        self,
        controller: SkylightController,
        entry: SkylightConfigEntry,
        command: str,
        name: str,
    ) -> None:
        super().__init__(controller, entry)
        self.command = command
        self._attr_name = name
        self._attr_unique_id = f"factory_mesh_7ffe_{command.lower().replace(' ', '_')}"
        self._attr_icon = "mdi:brightness-6" if command.startswith("dim") else "mdi:palette"

    async def async_press(self) -> None:
        await self.controller.async_send(self.command)


class SkylightPowerSyncButton(SkylightEntity, ButtonEntity):
    """Record an observation without transmitting a power command."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:eye-check-outline"

    def __init__(
        self, controller: SkylightController, entry: SkylightConfigEntry, is_on: bool
    ) -> None:
        super().__init__(controller, entry)
        self.is_on = is_on
        power = "on" if is_on else "off"
        self._attr_name = f"Record panel {power}"
        self._attr_unique_id = f"factory_mesh_7ffe_record_panel_{power}"

    async def async_press(self) -> None:
        async with self.controller.lock:
            self.controller.state.is_on = self.is_on
            self.controller.notify()
