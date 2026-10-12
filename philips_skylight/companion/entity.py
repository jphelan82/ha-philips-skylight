"""Shared proxy availability and device identity."""

from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED
from homeassistant.core import Event, callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_PROXY_ENTITY, DOMAIN
from .controller import SkylightController


class SkylightEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: SkylightController, entry) -> None:
        self.controller = controller
        self.proxy_entity = entry.data[CONF_PROXY_ENTITY]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "factory_mesh_7ffe")},
            name=entry.title,
            manufacturer="Philips",
            model="LED Skylight (NatureConnect / BioUp)",
        )

    @property
    def available(self) -> bool:
        proxy = self.hass.states.get(self.proxy_entity)
        return (
            proxy is not None
            and proxy.state not in ("unavailable", "unknown")
            and self.hass.services.has_service("esphome", self.controller.service)
        )

    @callback
    def _proxy_changed(self, event: Event) -> None:
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if old is None or old.state in ("unavailable", "unknown") or new is None:
            # Remote presses during downtime could have changed the physical power.
            self.controller.state.is_on = None
            self.controller.state.effect = None
            if new is not None and new.state not in ("unavailable", "unknown"):
                self.hass.async_create_task(self.controller.async_setup_receiver())
        if new is None or new.state in ("unavailable", "unknown"):
            self.controller.state.is_on = None
            self.controller.state.effect = None
        self.controller.notify()

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
        # Only the light owns the shared connection lifecycle to avoid duplicate setup calls.
        if self.platform.domain == "light":
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self.proxy_entity], self._proxy_changed)
            )
        for event_type in (EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED):
            self.async_on_remove(self.hass.bus.async_listen(event_type, self._service_changed))
