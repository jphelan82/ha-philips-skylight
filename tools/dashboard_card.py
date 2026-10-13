"""Build the standard Skylight card with a separate state-correction view."""

import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _integration_const():
    # Load const.py alone: the package __init__ imports Home Assistant.
    path = ROOT / "custom_components/philips_skylight/const.py"
    spec = importlib.util.spec_from_file_location("skylight_const", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EFFECTS = _integration_const().EFFECTS
LIGHT = "light.philips_skylight"
SCENE = "select.philips_skylight_recorded_scene"
EDIT = "switch.philips_skylight_state_correction"
OUTPUT = ROOT / "philips_skylight/app/static/skylight-card.yaml"
COMPACT_OUTPUT = OUTPUT.with_name("skylight-card-compact.yaml")
JSON_OUTPUT = OUTPUT.with_name("skylight-cards.json")


def action(service, entity, **data):
    result = {
        "action": "perform-action",
        "perform_action": service,
        "target": {"entity_id": entity},
    }
    if data:
        result["data"] = data
    return result


def tile(entity, name, tap, *, color="grey", icon=None):
    result = {
        "type": "tile",
        "entity": entity,
        "name": name,
        "hide_state": True,
        "color": color,
        "tap_action": tap,
        "icon_tap_action": tap,
    }
    if icon:
        result["icon"] = icon
    return result


def conditional(entity, state, card, *, inverse=False):
    return {
        "type": "conditional",
        "conditions": [
            {"condition": "state", "entity": entity, "state_not" if inverse else "state": state}
        ],
        "card": card,
    }


def highlighted(entity, state, button, name, tap, icon=None):
    # A stable grid slot contains exactly one of the two standard tiles.
    return {
        "type": "vertical-stack",
        "cards": [
            conditional(entity, state, tile(button, name, tap, color="blue", icon=icon)),
            conditional(entity, state, tile(button, name, tap, icon=icon), inverse=True),
        ],
    }


def grid(cards, columns=2):
    return {"type": "grid", "columns": columns, "square": False, "cards": cards}


def heading(text, icon=None):
    result = {"type": "heading", "heading": text, "heading_style": "subtitle"}
    if icon:
        result["icon"] = icon
    return result


def scenes(correction=False, compact=False):
    cards = []
    for effect in EFFECTS:
        button = "button.philips_skylight_" + effect.lower().replace(" ", "_")
        tap = (
            action("select.select_option", SCENE, option=effect)
            if correction
            else action("button.press", button)
        )
        slot = highlighted(SCENE, effect, button, effect, tap)
        if compact:
            for variant in slot["cards"]:
                variant["card"]["vertical"] = True
        cards.append(slot)
    return grid(cards, columns=3 if compact else 2)


def build_card(compact=False):
    status = {
        "type": "tile",
        "entity": LIGHT,
        "name": "Skylight",
        "state_content": ["state", "assumed_effect"],
        "icon": "mdi:power",
        "tap_action": action("light.toggle", LIGHT),
        "icon_tap_action": action("light.toggle", LIGHT),
    }
    normal = {
        "type": "vertical-stack",
        "cards": [
            status,
            heading("Modes"),
            scenes(compact=compact),
            grid(
                [
                    tile(
                        "button.philips_skylight_" + dim,
                        name,
                        action("button.press", "button.philips_skylight_" + dim),
                        icon=icon,
                    )
                    for dim, name, icon in [
                        ("dim_down", "Dim down", "mdi:brightness-4"),
                        ("dim_up", "Dim up", "mdi:brightness-7"),
                    ]
                ]
            ),
            tile(
                EDIT,
                "Correct recorded state",
                action("switch.turn_on", EDIT),
                icon="mdi:pencil-outline",
            ),
            {
                "type": "markdown",
                "content": "Tap the power icon to toggle the light. "
                "If the recorded state is wrong or unknown, use **Correct recorded state**.",
            },
        ],
    }
    correction = {
        "type": "vertical-stack",
        "cards": [
            heading("Correct recorded state", "mdi:eye-check-outline"),
            grid(
                [
                    highlighted(
                        LIGHT,
                        power,
                        "button.philips_skylight_record_panel_" + power,
                        "Panel is " + power,
                        action("button.press", "button.philips_skylight_record_panel_" + power),
                    )
                    for power in ("on", "off")
                ]
            ),
            heading("Mode I can see"),
            scenes(correction=True, compact=compact),
            tile(
                SCENE,
                "Mode unknown",
                action("select.select_option", SCENE, option="Unknown"),
                icon="mdi:help-circle-outline",
            ),
            tile(EDIT, "Done", action("switch.turn_off", EDIT), icon="mdi:check"),
            {
                "type": "markdown",
                "content": "Look at the physical panel. Select whether it "
                "is **on or off**, then select the mode you can see (or **Mode unknown**). "
                "These choices only correct Home Assistant's record; they **do not change the "
                "light**. Select **Done** to return to normal controls.",
            },
        ],
    }
    if compact:
        # Keep the observation instructions in correction mode; the everyday
        # card fits in one dashboard section without extra headings or prose.
        normal["cards"].pop(1)
        normal["cards"].pop()
    return {
        "type": "vertical-stack",
        "cards": [
            *(
                []
                if compact
                else [
                    {
                        "type": "heading",
                        "heading": "Skylight",
                        "heading_style": "title",
                        "icon": "mdi:ceiling-light",
                    }
                ]
            ),
            conditional(EDIT, "on", normal, inverse=True),
            conditional(EDIT, "on", correction),
        ],
    }


class CardDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def rendered_card(compact=False):
    return (
        "# Generated by tools/dashboard_card.py. Uses only standard Home Assistant cards.\n"
        "# The add-on download fills in your installation's actual entity IDs.\n"
        + yaml.dump(build_card(compact), Dumper=CardDumper, sort_keys=False, allow_unicode=True)
    )


def generated_files():
    return {
        OUTPUT: rendered_card(),
        COMPACT_OUTPUT: rendered_card(True),
        JSON_OUTPUT: json.dumps({"full": build_card(), "compact": build_card(True)}, indent=2)
        + "\n",
    }


if __name__ == "__main__":
    OUTPUT.write_text(rendered_card())
