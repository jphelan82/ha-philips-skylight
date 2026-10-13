# Skylight dashboard card

The Skylight card is built from Home Assistant's own tiles, grids, headings and
conditional cards. It needs no HACS card, dashboard resource, helper or
automation. The Skylight integration supplies the entities.

## The layout

The card uses the remote's icons and colors. It has three parts: a large
**Skylight** tile, the six mode buttons, and one row of small icon tiles.

| Control | Icon | What it does |
|---|---|---|
| **Skylight** | `mdi:ceiling-light` | Toggles the power. Shows the recorded power and mode. While the panel is on, it glows in the recorded mode's color, or amber when the mode is unknown. |
| Auto rhythm | `mdi:sun-clock-outline` | Follows the daily schedule. Purple when recorded. |
| Refresh | `mdi:weather-sunset-up` | Blue when recorded. |
| Energize | `mdi:lightning-bolt` | Light blue when recorded. |
| Focus | `mdi:crosshairs-gps` | Amber when recorded. |
| Relax | `mdi:sofa-outline` | Orange when recorded. |
| Rest | `mdi:power-sleep` | Deep orange when recorded. |
| **Dim −** / **Dim +** | `mdi:brightness-4` / `mdi:brightness-7` | A tap is one step. A hold dims for about 3 seconds. |
| **Rhythm set** | `mdi:clock-start` | Sets the current time as the Auto rhythm start. The panel blinks. |
| **Correct** | `mdi:pencil-outline` | Opens the correction view. |

The colors match the dots on the remote. A mode button also switches the panel
on. The mode that Home Assistant recorded lights up. The others stay grey. When
the mode is unknown, none lights up.

A tile card cannot tell when you let go. So a hold on a dim tile sends the
remote's hold command for about 3 seconds. On the add-on page, holding a dim
button keeps dimming until you let go.

You cannot set a brightness level. The panel takes only "dim down" and "dim up"
commands and never reports its level.

## Add the card

On the add-on page:

- **Create a Skylight dashboard** makes a dashboard with the card. If one
  already exists, the add-on opens it and changes nothing.
- **Add to a dashboard** adds the card to a view you choose and keeps the rest
  of that dashboard. A sections view gets a new section.

The add-on does not add the same card twice. If the dashboard changed since you
chose the view, choose it again first. Do not edit the same dashboard in another
window while the add-on adds the card.

For YAML dashboards, panel views and generated dashboards, select **Download the
card instead**. Then use **Edit dashboard → Add card → Manual** and paste it.
The download fills in your real entity IDs, renamed ones included. The
generated [card](../philips_skylight/app/static/skylight-card.yaml) is also in
this repository.

## Correct the state

The panel never reports its state, so the record can drift: a missed remote
press, a power cut, a wall switch, or an outage. To fix it:

1. Select **Correct**. The card switches to the correction view.
2. Select **Panel is on** or **Panel is off**.
3. Select the mode you can see, or **Mode unknown**.
4. Select **Done**.

These change only Home Assistant's record. They do not send anything to the
panel, and they do not use a command number. Received remote presses then keep
the record up to date. The correction view closes after a Home Assistant
restart.

## The entities

You can also add the entities to your own cards:

| Entity | What it does |
|---|---|
| Skylight light | One power toggle. `light.turn_on` and `light.turn_off` decide from the recorded power. |
| Six mode buttons | Sends that mode. The panel switches on in that mode. |
| Dim down / Dim up | Sends one step. |
| Set auto rhythm start | Sets the current time as the Auto rhythm start. |
| Record panel on / Record panel off | Records the power you can see. Sends nothing. |
| Recorded scene | Records the mode you can see. Sends nothing. |
| State correction | Switches the card between controls and correction. Sends nothing. |

The correction entities appear in the device's **Configuration** section. Keep
them enabled. Otherwise the card download names the missing entity instead of
making a broken card.
