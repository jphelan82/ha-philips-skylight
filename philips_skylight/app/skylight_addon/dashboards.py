"""Optional, additive dashboard setup through the native Lovelace API."""

import copy

from .ha import HAError

PATH = "skylight-control"
# The integration's own card. It builds the controls from the registry's entity IDs.
CARD = {"type": "custom:philips-skylight-card"}


async def list_dashboards(ha):
    if not ha.ready:
        raise HAError("Wait for Home Assistant to reconnect")
    dashboards = await ha.request("lovelace/dashboards/list")
    return [
        {"url_path": item["url_path"], "title": item.get("title", item["url_path"])}
        for item in dashboards
        if item.get("mode") == "storage"
    ]


async def create_dashboard(ha, card):
    if not ha.ready:
        raise HAError("Wait for Home Assistant to reconnect")
    existing = await ha.request("lovelace/dashboards/list")
    if PATH in {item["url_path"] for item in existing}:
        # Repeated setup clicks open the existing dashboard, never replace it.
        return {"url": f"/{PATH}", "created": False}
    await ha.request(
        "lovelace/dashboards/create",
        url_path=PATH,
        title="Skylight",
        icon="mdi:wall-sconce-flat",
        show_in_sidebar=True,
        require_admin=False,
    )
    config = {
        "views": [
            {
                "title": "Skylight",
                "path": "panel",
                "type": "sections",
                "max_columns": 1,
                "sections": [{"type": "grid", "cards": [card]}],
            }
        ],
    }
    try:
        await ha.request("lovelace/config/save", url_path=PATH, config=config)
    except HAError as err:
        # Do not replay a timed-out write or delete a possibly completed dashboard.
        raise HAError(
            "Dashboard was created, but its card save was not confirmed. "
            "Open Skylight and check it; use Add card if it is empty. " + str(err)
        ) from err
    return {"url": f"/{PATH}/panel", "created": True}


def is_skylight_card(value, switch):
    """Whether a card is the Skylight card, in any version.

    The current card is the integration's one-line card. Every older version is a
    vertical stack that ends with two conditional cards. They show the controls or
    the correction view from the state correction switch. The older Full card has a
    heading before them.
    """
    if isinstance(value, dict) and value.get("type") == CARD["type"]:
        return True
    if not isinstance(value, dict) or value.get("type") != "vertical-stack":
        return False
    cards = value.get("cards")
    if not isinstance(cards, list) or len(cards) < 2:
        return False
    if any(not isinstance(child, dict) or child.get("type") != "heading" for child in cards[:-2]):
        return False
    for child in cards[-2:]:
        if not isinstance(child, dict) or child.get("type") != "conditional":
            return False
        conditions = child.get("conditions")
        if not isinstance(conditions, list) or len(conditions) != 1:
            return False
        if not isinstance(conditions[0], dict) or conditions[0].get("entity") != switch:
            return False
    return True


def replace_cards(config, switch, card):
    """Return the config with every older Skylight card replaced, and the count replaced."""
    replaced = 0

    def walk(value):
        nonlocal replaced
        if is_skylight_card(value, switch):
            # The one-line card is never outdated, even with the user's own options.
            if value == card or value.get("type") == CARD["type"]:
                return value
            replaced += 1
            return copy.deepcopy(card)
        if isinstance(value, dict):
            return {key: walk(child) for key, child in value.items()}
        if isinstance(value, list):
            return [walk(child) for child in value]
        return value

    return walk(config), replaced


def _target(path):
    # The default dashboard is addressed by leaving url_path out.
    return {} if path is None else {"url_path": path}


async def _default_is_yaml(ha):
    """Whether the default dashboard is in YAML mode, which cannot be saved."""
    try:
        info = await ha.request("lovelace/info")
    except HAError:
        return False  # An older Home Assistant; update_cards reports a failed save instead.
    return isinstance(info, dict) and info.get("mode") == "yaml"


async def _dashboards_with_cards(ha):
    """Each editable dashboard's path, title and config. The default one has path None."""
    if not ha.ready:
        raise HAError("Wait for Home Assistant to reconnect")
    # list_dashboards gives only storage dashboards, so YAML ones are left out.
    found = await list_dashboards(ha)
    if not await _default_is_yaml(ha):
        found = [{"url_path": None, "title": "Overview"}] + found
    result = []
    for item in found:
        try:
            config = await ha.request("lovelace/config", **_target(item["url_path"]), force=True)
        except HAError:
            continue  # An automatic dashboard has no saved config.
        if isinstance(config, dict) and not config.get("strategy"):
            result.append({**item, "config": config})
    return result


async def outdated_cards(ha, switch, card):
    """Dashboards that hold an older Skylight card."""
    result = []
    for item in await _dashboards_with_cards(ha):
        _, replaced = replace_cards(item["config"], switch, card)
        if replaced:
            result.append({"url_path": item["url_path"], "title": item["title"]})
    return result


async def update_cards(ha, switch, card):
    """Replace every older Skylight card with the current one. Nothing else changes.

    A dashboard that fails to save does not stop the others. Its save is not retried.
    """
    updated, failed = [], []
    for item in await _dashboards_with_cards(ha):
        config, replaced = replace_cards(item["config"], switch, card)
        if replaced:
            try:
                await ha.request(
                    "lovelace/config/save", **_target(item["url_path"]), config=config
                )
            except HAError:
                failed.append(item["title"])
                continue
            updated.append(item["title"])
    return {"updated": updated, "failed": failed}
