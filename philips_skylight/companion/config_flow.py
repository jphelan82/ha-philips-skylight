"""UI configuration for a single factory mesh network."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import CONF_PROXY_ENTITY, CONF_TRANSMIT_SERVICE, DOMAIN


class SkylightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("factory_mesh_7ffe")
        self._abort_if_unique_id_configured()
        return await self._async_configure(user_input, "user")

    async def async_step_reconfigure(self, user_input=None):
        return await self._async_configure(user_input, "reconfigure", self._get_reconfigure_entry())

    async def _async_configure(self, user_input, step_id, entry=None):
        services = sorted(
            name
            for name in self.hass.services.async_services().get("esphome", {})
            if name.endswith("_adv_svc_v1")
        )
        errors = {}
        if user_input is not None:
            service = user_input[CONF_TRANSMIT_SERVICE]
            proxy = user_input[CONF_PROXY_ENTITY]
            if service not in services:
                errors["base"] = "transmitter_missing"
            elif self.hass.states.get(proxy) is None:
                errors[CONF_PROXY_ENTITY] = "proxy_missing"
            else:
                if entry is not None:
                    return self.async_update_reload_and_abort(
                        entry, title=user_input[CONF_NAME], data_updates=user_input
                    )
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        if not services:
            return self.async_abort(reason="no_transmitter")
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=entry.data[CONF_NAME] if entry else "Philips Skylight"
                    ): str,
                    vol.Required(
                        CONF_TRANSMIT_SERVICE,
                        default=entry.data[CONF_TRANSMIT_SERVICE] if entry else vol.UNDEFINED,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=services, mode="dropdown")
                    ),
                    vol.Required(
                        CONF_PROXY_ENTITY,
                        default=entry.data[CONF_PROXY_ENTITY] if entry else vol.UNDEFINED,
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor", integration="esphome")
                    ),
                }
            ),
            errors=errors,
        )
