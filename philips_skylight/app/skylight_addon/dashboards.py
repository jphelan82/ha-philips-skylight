"""Optional, additive dashboard setup through the native Lovelace API."""

import copy
import hashlib
import json
import re

from .ha import HAError

PATH = "skylight-control"


def revision(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def validate_path(path):
    if not isinstance(path, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", path):
        raise ValueError("Choose a dashboard from the list")
    return path


async def list_dashboards(ha):
    if not ha.ready:
        raise HAError("Wait for Home Assistant to reconnect")
    dashboards = await ha.request("lovelace/dashboards/list")
    return [
        {"url_path": item["url_path"], "title": item.get("title", item["url_path"])}
        for item in dashboards
        if item.get("mode") == "storage"
    ]


async def load_dashboard(ha, path):
    validate_path(path)
    if path not in {item["url_path"] for item in await list_dashboards(ha)}:
        raise ValueError("Choose an editable storage dashboard")
    return await ha.request("lovelace/config", url_path=path, force=True)


def editable_views(config):
    if config.get("strategy"):
        return []  # Never take control of an automatically generated dashboard.
    return [
        {"index": index, "title": view.get("title", f"View {index + 1}")}
        for index, view in enumerate(config.get("views", []))
        if not view.get("strategy")
        and view.get("type", "masonry") in ("sections", "masonry", "sidebar")
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


async def add_card(ha, path, index, expected_revision, card):
    config = await load_dashboard(ha, path)
    if not expected_revision or revision(config) != expected_revision:
        raise ValueError("Dashboard changed. Refresh the dashboard choices before adding the card")
    if type(index) is not int or index not in {view["index"] for view in editable_views(config)}:
        raise ValueError("Choose an editable view; strategy and panel views use manual card setup")
    updated = copy.deepcopy(config)
    view = updated["views"][index]

    def contains(value):
        if value == card:
            return True
        if isinstance(value, dict):
            return any(contains(child) for child in value.values())
        if isinstance(value, list):
            return any(contains(child) for child in value)
        return False

    if contains(view):
        return {"url": f"/{path}/{view.get('path', index)}", "added": False}
    if view.get("type") == "sections":
        view.setdefault("sections", []).append({"type": "grid", "cards": [card]})
    else:
        view.setdefault("cards", []).append(card)
    await ha.request("lovelace/config/save", url_path=path, config=updated)
    return {"url": f"/{path}/{view.get('path', index)}", "added": True}
