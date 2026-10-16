import copy

import pytest
from skylight_addon import dashboards
from skylight_addon.dashboards import create_dashboard
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
    new = dashboards.CARD
    other = {"type": "tile", "entity": "light.kitchen"}
    # The user gave this copy of the one-line card a width of its own.
    resized = {**new, "grid_options": {"columns": 6}}
    configs = {
        None: {"views": [{"cards": [other, skylight_card("old", heading=True)]}]},
        "kitchen": {"views": [{"sections": [{"cards": [skylight_card("old"), other]}]}]},
        "skylight-control": {"views": [{"sections": [{"cards": [new, resized]}]}]},
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
    assert configs["skylight-control"]["views"][0]["sections"][0]["cards"] == [new, resized]
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
    # The integration's one-line card is the current Skylight card, with any options.
    assert dashboards.is_skylight_card(dashboards.CARD, SWITCH)
    assert dashboards.is_skylight_card({**dashboards.CARD, "view_layout": {}}, "switch.other")
    assert not dashboards.is_skylight_card({"type": "custom:other-card"}, SWITCH)


async def test_automatic_dashboards_are_skipped():
    ha = ManyDashboardsHA({None: {"strategy": {"type": "original-states"}}})
    assert await dashboards.outdated_cards(ha, SWITCH, dashboards.CARD) == []


async def test_a_yaml_default_dashboard_is_skipped_and_a_failed_save_blocks_nothing():
    new = dashboards.CARD

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
