# Skylight dashboard card

The Skylight card combines Home Assistant's built-in tiles, grids, headings and
scene selector. It needs no HACS card, dashboard resource, helper or automation.
The companion integration supplies the entities.

## Add the card

1. Install/update the add-on and restart Home Assistant when requested.
2. Open the add-on and select **Download Home Assistant dashboard card**.
   This fills in the entity IDs from your installation, including renamed ones.
3. Open the dashboard you want to use, select **Edit dashboard**, then **Add card**
   and **Manual**. Paste the downloaded configuration and save.

The [static card](../philips_skylight/app/static/skylight-card.yaml) is also
available from this repository. Replace its entity IDs if yours differ. Once
added, the card is ordinary dashboard configuration: customize it in Home
Assistant or copy it to another dashboard. If you rename an entity afterward,
download the card again or update the affected dashboard references.

The native entities can also be added individually with the dashboard editor:

| Control | What it does |
|---|---|
| Skylight light | Sends normal on/off requests; opens the light's standard details. |
| Six scene buttons | Sends the selected scene to the panel. |
| Dim down / Dim up | Sends a relative dim step. |
| Record panel on / Record panel off | Records the power you can see; sends nothing. |
| Recorded scene | Records the scene you can see; sends nothing. Choose Unknown to clear it. |

## Correct a missed remote press

Look at the physical panel. Under **Correct recorded state**, press **Panel is on**
or **Panel is off**. If you know its scene, choose it under **Scene I can see**;
otherwise leave it Unknown. These controls update the light entity and the
integration's shared state immediately. They do not change the physical light,
the last transmitted/received command, or the Mesh sequence counter.

After synchronization, received remote toggles and scene presses keep that
state current. A toggle received while power is unknown cannot establish which
state is correct. Restart, proxy outage and missed reception still require an
observation. Absolute brightness is not tracked or editable because the panel's
relative dim step and physical level have not been measured.

The correction entities appear in the device's Configuration section. Keep them
enabled to use the complete card; the card download reports a missing or disabled
entity rather than generating broken controls. Normal commands remain available
through the standard light and button entities, even without this card.
