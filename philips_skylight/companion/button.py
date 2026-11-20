"""Known relative dim commands and direct scene selection."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DIM_ICONS,
    DOMAIN,
    EFFECT_STYLE,
    EFFECTS,
    RHYTHM_START,
    TOGGLE_VITA_UP,
    UNIQUE_ID_PREFIX,
)
from .controller import SkylightConfigEntry, SkylightController
from .entity import SkylightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkylightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    _enable_vita_up_from_0_8_0(hass)
    async_add_entities(
        SkylightButton(controller, entry, command, name)
        for command, name in (
            ("dim_down", "Dim down"),
            ("dim_up", "Dim up"),
            *((effect, effect) for effect in EFFECTS),
            (RHYTHM_START, "Set auto rhythm start"),
            (TOGGLE_VITA_UP, "Toggle Vita Up"),
        )
    )
    async_add_entities(
        SkylightPowerSyncButton(controller, entry, is_on) for is_on in (True, False)
    )


def _enable_vita_up_from_0_8_0(hass: HomeAssistant) -> None:
    """Add-on 0.8.0 created Toggle Vita Up disabled. Enable it, hidden.

    Only a button that the integration disabled changes. A button that its
    owner disabled stays disabled.
    """
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{UNIQUE_ID_PREFIX}{TOGGLE_VITA_UP}"
    )
    entry = registry.async_get(entity_id) if entity_id else None
    if entry and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
        registry.async_update_entity(
            entity_id,
            disabled_by=None,
            hidden_by=entry.hidden_by or er.RegistryEntryHider.INTEGRATION,
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
        if command == RHYTHM_START:
            # Sets the current time as the schedule start. The panel blinks.
            self._attr_icon = "mdi:clock-start"
        elif command == TOGGLE_VITA_UP:
            # Only Vita-Up panels have the UV-B light. Hidden keeps it off
            # auto-generated dashboards. Automations can still press it.
            self._attr_icon = "mdi:white-balance-sunny"
            self._attr_entity_registry_visible_default = False
        elif command in DIM_ICONS:
            self._attr_icon = DIM_ICONS[command]
        else:
            self._attr_icon = EFFECT_STYLE[command][0]

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

    @property
    def available(self) -> bool:
        # Records only and never transmits, so it works while the proxy is offline.
        return True

    async def async_press(self) -> None:
        async with self.controller.lock:
            self.controller.state.is_on = self.is_on
            self.controller.notify()
