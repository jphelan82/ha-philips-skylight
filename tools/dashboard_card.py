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


CONST = _integration_const()
EFFECTS = CONST.EFFECTS
# The remote's layout: Auto rhythm, Refresh, Energize, then Focus, Relax, Rest.
MODES = list(CONST.EFFECT_STYLE)
LIGHT = "light.philips_skylight"
SCENE = "select.philips_skylight_recorded_scene"
EDIT = "switch.philips_skylight_state_correction"
RHYTHM_START = "button.philips_skylight_set_auto_rhythm_start"
OUTPUT = ROOT / "philips_skylight/app/static/skylight-card.yaml"
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


def tile(entity, name, tap, *, color="grey", icon=None, hold=None):
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
    if hold:
        result["hold_action"] = hold
    return result


def conditional(entity, state, card, *, inverse=False):
    return {
        "type": "conditional",
        "conditions": [
            {"condition": "state", "entity": entity, "state_not" if inverse else "state": state}
        ],
        "card": card,
    }


def highlighted(entity, state, button, name, tap, icon=None, color="blue", when_on=False):
    # A stable grid slot contains exactly one of the two standard tiles.
    lit = conditional(entity, state, tile(button, name, tap, color=color, icon=icon))
    unlit = conditional(entity, state, tile(button, name, tap, icon=icon), inverse=True)
    if when_on:
        # An off panel shows no mode, like any light: light only while the panel is on.
        power = {"condition": "state", "entity": LIGHT, "state": "on"}
        lit["conditions"].append(power)
        unlit["conditions"] = [
            {"condition": "or", "conditions": [*unlit["conditions"], {**power, "state_not": "on"}]}
        ]
        del unlit["conditions"][0]["conditions"][-1]["state"]
    return {"type": "vertical-stack", "cards": [lit, unlit]}


def grid(cards, columns=2):
    return {"type": "grid", "columns": columns, "square": False, "cards": cards}


def heading(text, icon=None):
    result = {"type": "heading", "heading": text, "heading_style": "subtitle"}
    if icon:
        result["icon"] = icon
    return result


def scenes(correction=False):
    cards = []
    for effect in MODES:
        icon, color = CONST.EFFECT_STYLE[effect]
        button = "button.philips_skylight_" + effect.lower().replace(" ", "_")
        tap = (
            action("select.select_option", SCENE, option=effect)
            if correction
            else action("button.press", button)
        )
        slot = highlighted(
            SCENE, effect, button, effect, tap, icon=icon, color=color, when_on=not correction
        )
        for variant in slot["cards"]:
            variant["card"]["vertical"] = True
        cards.append(slot)
    return grid(cards, columns=3)


def hero():
    """The panel's tile. It glows in the recorded mode's color while the panel is on."""
    tap = action("light.toggle", LIGHT)

    def variant(color):
        return {
            "type": "tile",
            "entity": LIGHT,
            "name": "Skylight",
            "icon": "mdi:ceiling-light",
            "color": color,
            "state_content": ["state", "assumed_effect"],
            "tap_action": tap,
            "icon_tap_action": tap,
        }

    # A stable slot holds exactly one variant. The tile itself turns grey when off.
    cards = [
        {
            "type": "conditional",
            "conditions": [{"condition": "state", "entity": SCENE, "state": mode}],
            "card": variant(CONST.EFFECT_STYLE[mode][1]),
        }
        for mode in MODES
    ]
    cards.append(
        {
            "type": "conditional",
            "conditions": [
                {"condition": "state", "entity": SCENE, "state_not": mode} for mode in MODES
            ],
            "card": variant("amber"),
        }
    )
    return {"type": "vertical-stack", "cards": cards}


def small(entity, name, tap, icon, hold=None):
    card = tile(entity, name, tap, icon=icon, hold=hold)
    card["vertical"] = True
    return card


def build_card():
    tools = grid(
        [
            *(
                small(
                    "button.philips_skylight_" + dim,
                    name,
                    action("button.press", "button.philips_skylight_" + dim),
                    CONST.DIM_ICONS[dim],
                    # A card cannot see the finger lift: a hold is 3 seconds on the remote.
                    hold=action(f"{CONST.DOMAIN}.dim", LIGHT, direction=dim[4:], hold=3),
                )
                for dim, name in (("dim_down", "Dim −"), ("dim_up", "Dim +"))
            ),
            small(
                RHYTHM_START, "Rhythm set", action("button.press", RHYTHM_START), "mdi:clock-start"
            ),
            small(EDIT, "Correct", action("switch.turn_on", EDIT), "mdi:pencil-outline"),
        ],
        columns=4,
    )
    normal = {"type": "vertical-stack", "cards": [hero(), scenes(), tools]}
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
                        icon=icon,
                        color="amber",
                    )
                    for power, icon in (
                        ("on", "mdi:lightbulb-on-outline"),
                        ("off", "mdi:lightbulb-off-outline"),
                    )
                ]
            ),
            heading("Mode"),
            scenes(correction=True),
            tile(
                SCENE,
                "Mode unknown",
                action("select.select_option", SCENE, option="Unknown"),
                icon="mdi:help-circle-outline",
            ),
            tile(EDIT, "Done", action("switch.turn_off", EDIT), icon="mdi:check"),
            {
                "type": "markdown",
                "content": "Look at the panel, then tap what you see. This changes only "
                "what Home Assistant shows. It does not change the light.",
            },
        ],
    }
    return {
        "type": "vertical-stack",
        "cards": [
            conditional(EDIT, "on", normal, inverse=True),
            conditional(EDIT, "on", correction),
        ],
    }


class CardDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def rendered_card():
    return (
        "# Generated by tools/dashboard_card.py. Uses only standard Home Assistant cards.\n"
        "# The add-on download fills in your installation's actual entity IDs.\n"
        + yaml.dump(build_card(), Dumper=CardDumper, sort_keys=False, allow_unicode=True)
    )


def generated_files():
    return {
        OUTPUT: rendered_card(),
        JSON_OUTPUT: json.dumps({"card": build_card()}, indent=2) + "\n",
    }


if __name__ == "__main__":
    OUTPUT.write_text(rendered_card())
