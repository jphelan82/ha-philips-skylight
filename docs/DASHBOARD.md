# Skylight dashboard card

The Skylight integration includes its own card, **Philips Skylight**. The card
shows Home Assistant's own tiles, grids, headings and conditional cards. It
needs no HACS (the Home Assistant Community Store), no download, no dashboard
resource, no helper and no automation. The integration supplies the entities
and the card. The card finds each entity by its unique ID in the entity
registry, so renamed entities keep working.

## The layout

The card uses the remote's icons and colors. It has three parts: a large
**Skylight** tile, the six mode buttons, and one row of small icon tiles.

| Control | Icon | What it does |
|---|---|---|
| **Skylight** | `mdi:wall-sconce-flat` | Toggles the power. Shows the recorded power and mode. While the panel is on, it glows in the recorded mode's color, or amber when the mode is unknown. |
| Auto rhythm | `mdi:sun-clock-outline` | Follows the daily schedule. Purple when recorded. |
| Refresh | `mdi:weather-sunset-up` | Blue when recorded. |
| Energize | `mdi:lightning-bolt` | Light blue when recorded. |
| Focus | `mdi:crosshairs-gps` | Amber when recorded. |
| Relax | `mdi:sofa-outline` | Orange when recorded. |
| Rest | `mdi:power-sleep` | Deep orange when recorded. |
| **Correct** | `mdi:pencil-outline` | Opens the correction view. |
| **Rhythm set** | `mdi:clock-start` | Sets the current time as the Auto rhythm start. The panel blinks. |
| **Dim −** / **Dim +** | `mdi:brightness-4` / `mdi:brightness-7` | A tap is one step. A hold dims for about 3 seconds, after you let go. |

The colors match the dots on the remote. A mode button also switches the panel
on. The mode that Home Assistant recorded lights up. The others stay grey. When
the mode is unknown, none lights up.

A hold on a dim tile works differently from a hold on the remote:

- Home Assistant shows a circle when a press counts as a hold, after about half
  a second.
- Home Assistant sends the hold when you let go, not while you hold. Then the
  panel dims for about 3 seconds.
- If your finger moves during the press, Home Assistant cancels it and sends
  nothing. Keep your finger still.

Home Assistant's own cards cannot dim while you hold. On the add-on page,
holding a dim button keeps dimming until you let go, like the remote.

You cannot set a brightness level. The panel takes only "dim down" and "dim up"
commands and never reports its level.

## Add the card

Use Home Assistant's card picker:

1. Open a dashboard, then select **Edit dashboard**.
2. Select **Add card**.
3. Open the **By card** tab. The dialog opens on **By entity**, which lists
   entities only.
4. Search for **Philips Skylight**, then select it.
5. Select **Save**.

The card needs no options. Its YAML is one line:

```yaml
type: custom:philips-skylight-card
```

Home Assistant loads the card's script when a browser opens Home Assistant. If
the card is not in the card picker after the first install, reload the page in
your browser.

The add-on page also has two shortcuts:

- **Create a Skylight dashboard** makes a dashboard with the card. If one
  already exists, the add-on opens it and changes nothing.
- **Download the card instead** saves the standard cards as YAML, with your
  real entity IDs. Use it to change the layout. Select **Edit dashboard → Add
  card → Manual** and paste it. The generated
  [card](../philips_skylight/app/static/skylight-card.yaml) is also in this
  repository.

Older versions of the add-on put the full stack of standard cards on a
dashboard. If a dashboard holds such a copy, the add-on page shows **Update the
card**. It replaces that copy with the one-line card.

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
them enabled. If an entity that the card uses is disabled, the card names that
entity instead of showing broken controls. The card download does the same.
