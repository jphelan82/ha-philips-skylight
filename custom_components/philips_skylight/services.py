"""Skylight actions. They reach the controller even while the light is unavailable."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids

from .const import DOMAIN
from .controller import SkylightController

PAIR_CONFIRM = (
    "Switch the panel's power off and on at its light switch or breaker. As soon as "
    "it is back on, start pairing with confirm set to true."
)
UNPAIR_CONFIRM = (
    "Unpairing removes every remote, the original one included, and this "
    "transmitter. Set confirm to true only if you will pair them all again."
)
SKIP_CONFIRM = (
    "Skip the sequence only when the panel ignores this transmitter after "
    "Home Assistant was rebuilt or restored from an older backup."
)


def _confirm(message: str) -> dict:
    # Reject a missing confirmation in the schema, so the REST API answers 400.
    return {vol.Required("confirm"): vol.All(cv.boolean, vol.IsTrue(message))}


# Entity actions skip an unavailable light. These are domain actions instead, so
# recording the power and skipping the sequence work while the proxy is offline,
# and an action that must transmit fails with an error rather than doing nothing.
ACTIONS = {
    "set_assumed_power": (
        {vol.Required("is_on"): cv.boolean},
        lambda controller, data: controller.async_set_assumed_power(data["is_on"]),
    ),
    "pair_transmitter": (_confirm(PAIR_CONFIRM), lambda controller, data: controller.async_pair()),
    "unpair_all_remotes": (
        _confirm(UNPAIR_CONFIRM),
        lambda controller, data: controller.async_unpair_all(),
    ),
    "dim": (
        {
            vol.Required("direction"): vol.In(["down", "up"]),
            vol.Optional("hold", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        },
        lambda controller, data: controller.async_dim(data["direction"], data["hold"]),
    ),
    "skip_sequence": (
        _confirm(SKIP_CONFIRM),
        lambda controller, data: controller.async_skip_sequence(),
    ),
}


async def _async_controllers(call: ServiceCall) -> list[SkylightController]:
    hass = call.hass
    if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
    else:
        registry = er.async_get(hass)
        entries = []
        for entity_id in await async_extract_entity_ids(call):
            entity = registry.async_get(entity_id)
            if entity is None or entity.platform != DOMAIN or entity.domain != "light":
                continue
            entry = hass.config_entries.async_get_entry(entity.config_entry_id)
            if entry is not None and entry.state is ConfigEntryState.LOADED:
                entries.append(entry)
    controllers = []
    for entry in entries:
        if entry.runtime_data not in controllers:
            controllers.append(entry.runtime_data)
    if not controllers:
        raise ServiceValidationError("Select a Philips Skylight light that is set up.")
    return controllers


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    for name, (fields, action) in ACTIONS.items():

        async def handle(call: ServiceCall, action=action) -> None:
            for controller in await _async_controllers(call):
                await action(controller, call.data)

        hass.services.async_register(DOMAIN, name, handle, cv.make_entity_service_schema(fields))
