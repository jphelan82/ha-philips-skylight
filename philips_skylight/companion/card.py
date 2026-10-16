"""The Skylight dashboard card: its script, and the card config it asks for."""

import json
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util.hass_dict import HassKey

from .const import CARD_ENTITIES, CARD_URL, DOMAIN, VERSION

HERE = Path(__file__).parent
SCRIPT = HERE / "frontend/philips-skylight-card.js"
TEMPLATE = HERE / "card.json"
CARD_TEMPLATE: HassKey[dict[str, Any]] = HassKey(f"{DOMAIN}_card_template")


class CardError(Exception):
    """A control entity that the card needs is missing or disabled."""


async def async_setup_card(hass: HomeAssistant) -> None:
    """Serve the card script, load it on every frontend page, and answer its request."""
    hass.data[CARD_TEMPLATE] = await hass.async_add_executor_job(
        lambda: json.loads(TEMPLATE.read_text())
    )
    websocket_api.async_register_command(hass, websocket_card)
    # Tests run without the web server and the frontend.
    if hass.http is not None:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(SCRIPT), cache_headers=False)]
        )
    if "frontend" in hass.config.components:
        # The version makes a browser load the new script after an update.
        add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")


def card_entities(hass: HomeAssistant) -> dict[str, str]:
    """Map each default entity ID in the template to its current entity ID."""
    registry = er.async_get(hass)
    replacements = {}
    for default, unique_id in CARD_ENTITIES.items():
        entity_id = registry.async_get_entity_id(default.split(".")[0], DOMAIN, unique_id)
        if entity_id is None:
            raise CardError(
                f"The Skylight card needs the entity {default}, and Home Assistant has none. "
                "Set up the Philips Skylight integration, or reload it."
            )
        if registry.async_get(entity_id).disabled_by is not None:
            raise CardError(
                f"The Skylight card needs the entity {entity_id}. Enable it in "
                "Settings → Devices & services → Entities."
            )
        replacements[default] = entity_id
    return replacements


def card_config(hass: HomeAssistant) -> dict[str, Any]:
    """The standard cards, with the registry's entity IDs, renamed ones included."""
    replacements = card_entities(hass)

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(child) for key, child in value.items()}
        if isinstance(value, list):
            return [replace(child) for child in value]
        # Replace each whole value once, so a renamed entity that matches another default is safe.
        return replacements.get(value, value) if isinstance(value, str) else value

    return replace(hass.data[CARD_TEMPLATE])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/card"})
@callback
def websocket_card(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the card config. Any signed-in user can read it. It changes nothing."""
    try:
        card = card_config(hass)
    except CardError as err:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, str(err))
        return
    connection.send_result(msg["id"], {"card": card})
