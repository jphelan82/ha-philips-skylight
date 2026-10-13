import copy

import pytest
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
