import copy

import pytest
from skylight_addon import dashboards
from skylight_addon.dashboards import (
    add_card,
    create_dashboard,
    editable_views,
    revision,
)
from skylight_addon.ha import HAError


class DashboardHA:
    ready = True

    def __init__(self, config=None):
        self.config = config or {"views": []}
        self.dashboards = [{"url_path": "my-home", "mode": "storage", "title": "Home"}]
        self.calls = []
        self.fail_save = False

    async def request(self, kind, **data):
        self.calls.append((kind, data))
        if kind == "lovelace/dashboards/list":
            return copy.deepcopy(self.dashboards)
        if kind == "lovelace/dashboards/create":
            self.dashboards.append({**data, "mode": "storage"})
        elif kind == "lovelace/config":
            return copy.deepcopy(self.config)
        elif kind == "lovelace/config/save":
            if self.fail_save:
                raise HAError("Request timed out; not retried")
            self.config = copy.deepcopy(data["config"])
        else:
            raise AssertionError(kind)


async def test_optional_create_preserves_existing_dashboard_and_does_not_retry():
    ha = DashboardHA()
    card = {"type": "tile", "entity": "light.skylight"}
    result = await create_dashboard(ha, card)
    assert result["created"]
    assert ha.config["views"][0]["sections"][0]["cards"] == [card]
    existing = copy.deepcopy(ha.config)
    ha.calls.clear()
    result = await create_dashboard(ha, {"different": "card"})
    assert not result["created"]
    assert ha.config == existing
    assert [kind for kind, _ in ha.calls] == ["lovelace/dashboards/list"]
    ha = DashboardHA()
    ha.fail_save = True
    with pytest.raises(HAError, match="check it"):
        await create_dashboard(ha, card)
    assert sum(kind == "lovelace/config/save" for kind, _ in ha.calls) == 1
    assert not any("delete" in kind for kind, _ in ha.calls)


@pytest.mark.parametrize("view_type", ["sections", "masonry", "sidebar"])
async def test_add_card_preserves_views_and_user_config_and_is_idempotent(view_type):
    view = {"title": "Living room", "path": "living", "type": view_type, "theme": "Custom"}
    existing = {"type": "tile", "entity": "switch.other"}
    if view_type == "sections":
        view["sections"] = [{"type": "grid", "cards": [existing], "column_span": 2}]
    else:
        view["cards"] = [existing]
    original = {"background": {"image": "/local/bg.jpg"}, "views": [view, {"title": "Other"}]}
    ha = DashboardHA(copy.deepcopy(original))
    card = {"type": "vertical-stack", "cards": [{"type": "tile", "entity": "light.skylight"}]}
    result = await add_card(ha, "my-home", 0, revision(original), card)
    assert result == {"url": "/my-home/living", "added": True}
    assert ha.config["views"][1] == original["views"][1]
    assert ha.config["background"] == original["background"]
    if view_type == "sections":
        assert ha.config["views"][0]["sections"][0] == view["sections"][0]
    else:
        assert ha.config["views"][0]["cards"][0] == existing
    ha.calls.clear()
    result = await add_card(ha, "my-home", 0, revision(ha.config), card)
    assert not result["added"]
    assert not any(kind.endswith("/save") for kind, _ in ha.calls)


async def test_stale_strategy_panel_yaml_and_invalid_targets_never_save():
    ha = DashboardHA({"views": [{"title": "Home", "type": "sections"}]})
    with pytest.raises(ValueError, match="changed"):
        await add_card(ha, "my-home", 0, "old revision", {})
    for config in (
        {"strategy": {"type": "original-states"}, "views": []},
        {"views": [{"strategy": {"type": "custom:generated"}}]},
        {"views": [{"type": "panel", "cards": []}]},
    ):
        ha.config = config
        assert editable_views(config) == []
        with pytest.raises(ValueError, match="editable view"):
            await add_card(ha, "my-home", 0, revision(config), {})
    with pytest.raises(ValueError, match="editable storage"):
        await add_card(ha, "missing-dashboard", 0, revision(ha.config), {})
    with pytest.raises(ValueError, match="dashboard from"):
        await add_card(ha, "//evil.example", 0, revision(ha.config), {})
    assert not any(kind.endswith("/save") for kind, _ in ha.calls)


SWITCH = "switch.skylight_correction"


def skylight_card(label, heading=False):
    """A Skylight card in its outer shape. The label stands in for the controls."""
    cards = [
        {
            "type": "conditional",
            "conditions": [{"condition": "state", "entity": SWITCH, "state_not": "on"}],
            "card": {"type": "markdown", "content": label},
        },
        {
            "type": "conditional",
            "conditions": [{"condition": "state", "entity": SWITCH, "state": "on"}],
            "card": {"type": "markdown", "content": "correct"},
        },
    ]
    if heading:
        cards.insert(0, {"type": "heading", "heading": "Skylight"})
    return {"type": "vertical-stack", "cards": cards}


class ManyDashboardsHA:
    """Several dashboards: the default one, two storage ones, and a YAML one."""

    ready = True

    def __init__(self, configs, default_mode="storage"):
        self.configs = configs
        self.default_mode = default_mode
        self.saved = []
        self.fail_save = set()

    async def request(self, kind, **data):
        if kind == "lovelace/info":
            if self.default_mode is None:
                raise HAError("Unknown command.")  # An older Home Assistant.
            return {"mode": self.default_mode}
        if kind == "lovelace/dashboards/list":
            return [
                {"url_path": "kitchen", "title": "Kitchen", "mode": "storage"},
                {"url_path": "skylight-control", "title": "Skylight", "mode": "storage"},
                {"url_path": "yaml-one", "title": "YAML", "mode": "yaml"},
            ]
        path = data.get("url_path")
        if kind == "lovelace/config":
            if path not in self.configs:
                raise HAError("config_not_found")
            return copy.deepcopy(self.configs[path])
        if kind == "lovelace/config/save":
            if path in self.fail_save:
                raise HAError("config_not_supported")
            self.saved.append(path)
            self.configs[path] = copy.deepcopy(data["config"])
            return None
        raise AssertionError(kind)


async def test_older_cards_are_found_and_replaced_in_place():
    new = skylight_card("new")
    other = {"type": "tile", "entity": "light.kitchen"}
    configs = {
        None: {"views": [{"cards": [other, skylight_card("old", heading=True)]}]},
        "kitchen": {"views": [{"sections": [{"cards": [skylight_card("old"), other]}]}]},
        "skylight-control": {"views": [{"sections": [{"cards": [new]}]}]},
    }
    ha = ManyDashboardsHA(configs)
    found = await dashboards.outdated_cards(ha, SWITCH, new)
    assert [item["title"] for item in found] == ["Overview", "Kitchen"]
    assert ha.saved == []

    result = await dashboards.update_cards(ha, SWITCH, new)
    assert result == {"updated": ["Overview", "Kitchen"], "failed": []}
    # The default dashboard is saved without a url_path, and the current card is left alone.
    assert ha.saved == [None, "kitchen"]
    assert configs[None]["views"][0]["cards"] == [other, new]
    assert configs["kitchen"]["views"][0]["sections"][0]["cards"] == [new, other]
    assert await dashboards.outdated_cards(ha, SWITCH, new) == []


async def test_only_the_skylight_card_shape_matches():
    card = skylight_card("old")
    assert dashboards.is_skylight_card(card, SWITCH)
    assert dashboards.is_skylight_card(skylight_card("old", heading=True), SWITCH)
    assert not dashboards.is_skylight_card(card, "switch.other")
    tile_first = copy.deepcopy(card)
    tile_first["cards"].insert(0, {"type": "tile", "entity": "light.kitchen"})
    assert not dashboards.is_skylight_card(tile_first, SWITCH)
    assert not dashboards.is_skylight_card({"type": "vertical-stack", "cards": []}, SWITCH)


async def test_automatic_dashboards_are_skipped():
    ha = ManyDashboardsHA({None: {"strategy": {"type": "original-states"}}})
    assert await dashboards.outdated_cards(ha, SWITCH, skylight_card("new")) == []


async def test_a_view_with_sections_but_no_type_gets_a_new_section():
    # Home Assistant shows such a view as sections and hides its old card list.
    view = {"title": "Home", "sections": [{"type": "grid", "cards": []}]}
    ha = DashboardHA({"views": [view]})
    card = {"type": "tile", "entity": "light.skylight"}
    result = await add_card(ha, "my-home", 0, revision(ha.config), card)
    assert result["added"] is True
    saved = ha.config["views"][0]
    assert "cards" not in saved
    assert saved["sections"][-1] == {"type": "grid", "cards": [card]}
    assert dashboards.view_type({"cards": []}) == "masonry"
    assert dashboards.view_type({"type": "panel", "sections": []}) == "panel"


async def test_a_yaml_default_dashboard_is_skipped_and_a_failed_save_blocks_nothing():
    new = skylight_card("new")

    def configs():
        return {
            None: {"views": [{"cards": [skylight_card("old")]}]},
            "kitchen": {"views": [{"cards": [skylight_card("old")]}]},
        }

    ha = ManyDashboardsHA(configs(), default_mode="yaml")
    assert [item["title"] for item in await dashboards.outdated_cards(ha, SWITCH, new)] == [
        "Kitchen"
    ]
    assert await dashboards.update_cards(ha, SWITCH, new) == {"updated": ["Kitchen"], "failed": []}
    assert ha.saved == ["kitchen"]

    # An older Home Assistant cannot say the mode. The failed save does not stop the others.
    ha = ManyDashboardsHA(configs(), default_mode=None)
    ha.fail_save = {None}
    result = await dashboards.update_cards(ha, SWITCH, new)
    assert result == {"updated": ["Kitchen"], "failed": ["Overview"]}
    assert ha.saved == ["kitchen"]
