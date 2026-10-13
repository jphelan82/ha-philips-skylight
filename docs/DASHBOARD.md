# Skylight dashboard card

The Skylight card combines Home Assistant's built-in tiles, grids, headings and
conditional cards. It needs no HACS card, dashboard resource, helper or automation.
The companion integration supplies the entities.

## Optional dashboard setup

You do not need a dedicated dashboard to finish setup or use the integration.
Match the starting state in the add-on, then optionally choose **Compact** or
**Full** in its **Dashboard controls** section:

- **Create Skylight dashboard** creates the dedicated dashboard. If it exists,
  it is opened without changing its configuration.
- **Add card to an existing dashboard** adds the card to an editable view you
  select, preserving the rest of that dashboard. Sections views get a new
  section; masonry/sidebar views get an additional card.

Compact fits a shared dashboard with a three-column mode grid and less prose.
Full keeps headings and everyday instructions. Both retain the selected mode's
blue icon, gray unselected icons and the separate state-correction view.

For manual installation, download the chosen card in the add-on, then use
**Edit dashboard → Add card → Manual** and paste it. The download fills in
actual entity IDs, including renamed ones. This is also the route for YAML
and panel views. Automatically generated dashboards must first be taken over
through Home Assistant if you want to edit their cards; the add-on never does
that for you.

An identical card is not added twice, and a dashboard changed since you selected
its view must be refreshed before adding. Existing controls are preserved.
Home Assistant's API does not provide an atomic compare-and-save operation;
avoid editing the same dashboard in another session during an add-card request.

The generated [full card](../philips_skylight/app/static/skylight-card.yaml) and
[compact card](../philips_skylight/app/static/skylight-card-compact.yaml) are also
available in this repository. Replace entity IDs if yours differ. These are
ordinary built-in card configurations, not a registered custom type in the card
picker. Once added, customize them in Home Assistant or copy them elsewhere.
After an entity rename, download the card again or update its references.

**Before first use**, record the panel's observed power and mode in the add-on,
or use **Correct recorded state** on the card. In the add-on's **Record initial
state** form, optionally press a mode button on the existing control panel;
the mode dropdown always follows received presses. Choosing
a mode manually records it immediately without operating the light. Choose **Mode unknown** if unsure.
Repeat after pairing. Dashboard creation does not operate the light or set an
observed baseline for you.

The native entities can also be added individually with the dashboard editor:

| Control | What it does |
|---|---|
| Skylight light | The card sends one power toggle. Standard HA on/off actions remain available. |
| Six scene buttons | Sends the selected scene to the panel. |
| Dim down / Dim up | Sends a relative dim step. |
| Record panel on / Record panel off | Records the power you can see; sends nothing. |
| Recorded scene | Records the scene you can see; sends nothing. Choose Unknown to clear it. |
| State correction | Switches the card between normal controls and state correction; sends nothing. |

In normal control, the selected mode icon is blue and the other mode icons are
gray. Highlighting follows the recorded scene, including received remote scene
commands; no mode is highlighted when the scene is unknown. Tap the power tile
to send one toggle, matching the original remote. Dim controls send one relative
step per tap. The physical remote's held dim packets are recognized, but holding
a dashboard tile does not continuously dim the panel.

## Correct a missed remote press

Select **Correct recorded state** at the bottom of the card. The entire control
panel changes to a correction view. Look at the physical panel and select
**Panel is on** or **Panel is off**, then the mode you can see. Choose **Mode unknown**
if you cannot identify it. Select **Done** to return to normal controls.
These controls update the light entity and the
integration's shared state immediately. They do not change the physical light,
the last transmitted/received command, or the Mesh sequence counter.

After synchronization, received remote toggles and scene presses keep that
state updated, including compatible calls from other remote/control panels.
A toggle received while power is unknown cannot establish which
state is correct. Restart, proxy outage and missed reception still require an
observation. Absolute brightness is not tracked or editable because the panel's
relative dim step and physical level have not been measured.

Tracking can drift because of missed BLE events, power switches, mains cycles,
Home Assistant/proxy downtime, ignored commands or other compatible controllers
within range. The power label and blue mode icon are estimates. If this proves
unreliable, use the normal panel's power toggle, mode buttons and dim steps as
direct commands and observe the physical result. Avoid state-dependent
automations or relying on entity states as confirmation. In automations, use
`light.toggle` and the appropriate `button.press`; standard on/off actions rely
on the recorded baseline to decide whether to toggle.

The correction entities appear in the device's Configuration section. Keep them
enabled to use the complete card; the card download reports a missing or disabled
entity rather than generating broken controls. Normal commands remain available
through the standard light and button entities, even without this card.

Correction mode is a native HA switch shared by cards for this integration. It
returns to normal mode after an integration reload or Core restart. Opening or
closing this view does not alter the light's recorded power or scene.
