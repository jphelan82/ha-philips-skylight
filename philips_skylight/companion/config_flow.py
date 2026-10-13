"""UI configuration for a single factory mesh network."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import CONF_PROXY_ENTITY, CONF_TRANSMIT_SERVICE, DOMAIN


class SkylightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SkylightOptionsFlow()

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


class SkylightOptionsFlow(config_entries.OptionsFlow):
    """Configure: pair this transmitter, or make the panel forget every sender."""

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["pair", "unpair_all"])

    async def async_step_pair(self, user_input=None):
        return await self._async_pairing_step("pair", user_input)

    async def async_step_unpair_all(self, user_input=None):
        return await self._async_pairing_step("unpair_all", user_input)

    async def _async_pairing_step(self, step_id, user_input):
        errors = {}
        if user_input is not None:
            controller = getattr(self.config_entry, "runtime_data", None)
            if not user_input.get("confirm"):
                errors["base"] = "confirm_required"
            elif controller is None:
                return self.async_abort(reason="not_loaded")
            else:
                try:
                    if step_id == "pair":
                        await controller.async_pair()
                    else:
                        await controller.async_unpair_all()
                except HomeAssistantError:
                    errors["base"] = "send_failed"
                else:
                    return self.async_abort(reason=f"{step_id}_sent")
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            errors=errors,
        )
