"""Shared proxy availability and device identity."""

from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED
from homeassistant.core import Event, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import SkylightConfigEntry, SkylightController


class SkylightEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: SkylightController, entry: SkylightConfigEntry) -> None:
        self.controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "factory_mesh_7ffe")},
            name=entry.title,
            manufacturer="Philips",
            model="LED Skylight (NatureConnect / BioUp)",
        )

    @property
    def available(self) -> bool:
        return self.controller.transmitter_ready

    @callback
    def _service_changed(self, event: Event) -> None:
        if (
            event.data.get("domain") == "esphome"
            and event.data.get("service") == self.controller.service
        ):
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.controller.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.controller.listeners.discard(self.async_write_ha_state))
        # The controller follows the proxy and calls notify when it changes.
        for event_type in (EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED):
            self.async_on_remove(self.hass.bus.async_listen(event_type, self._service_changed))
