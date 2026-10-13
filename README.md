# Philips Skylight for Home Assistant

Control your Philips Skylight from a Home Assistant dashboard: toggle power,
choose a mode, and dim or brighten the panel. Your original remote can still be
used. We also listen for BLE button presses from other compatible remote/control
panels in range and use those received commands to update Home Assistant's record.

The add-on uses an ESPHome Bluetooth proxy. **No MQTT broker, cloud account,
custom dashboard card, or additional Bluetooth adapter is required.**

## What you need

- Home Assistant OS or Supervised, with Core 2026.6 or newer.
- A Philips Skylight panel. The NatureConnect/BioUp 17.7 × 25.6 inch model has
  been tested; other models have not yet been verified.
- An ESPHome Bluetooth proxy configured to send Skylight commands. The add-on
  provides the firmware configuration if your proxy needs updating. Firmware
  has been tested with an ESP32-C3 and ESPHome 2026.4.5.

For Home Assistant Container or Core installations without add-on support,
see the [integration-only installation guide](docs/INTEGRATION.md).

Multiple compatible panels within radio range may respond together; independent
control of individual nearby panels is not supported.

## Install and set up

1. In Home Assistant, open **Settings → Apps → App store → Repositories**
   (called **Add-ons** on older versions). Add:
   `https://github.com/jphelan82/ha-philips-skylight`.
2. Install **Philips Skylight**, enable **Start on boot**, start it, and open
   its web UI.
3. If the add-on asks you to restart Home Assistant, do so to activate the
   light integration.
4. Follow the add-on's guided setup. If your proxy needs firmware,
   download the ESPHome package and add its single `packages`/`!include` entry
   to the existing node configuration. Keep the node's Wi-Fi, API, OTA and board
   settings. Compile and install with ESPHome Device Builder. See the
   [package instructions](esphome/README.md).
5. Choose your **Bluetooth proxy** and save. A single compatible proxy is
   selected for you; advanced action/sensor selectors remain available for
   custom configurations.
6. In the proxy's ESPHome integration options, enable **Allow the device to
   perform Home Assistant actions** so received remote presses can update state.
7. **Pair the HA transmitter on first setup**, following the explicit pairing
   step below. An already paired, working installation can skip this; updating
   the add-on does not require re-pairing.
8. **Match the state before first use** using the add-on's **Record starting
   state** form. Observe the panel and record its power and mode, or choose
   **Unknown** for the mode. This works without a dashboard.
9. **Optional:** create a Skylight dashboard or add its card to an existing one.
   You can instead use the native entities in your own dashboard or automations.

Repository installation requires a published add-on on the repository's default
branch and access to that repository. If the add-on is not yet available in the
store, use the [local development installation](docs/PROTOCOL.md#development-installation).

After first setup, firmware, transmitter settings, permission guidance and
pairing are collapsed under **Setup and recovery**. If the recorded power is
unknown, **Match recorded state** opens so you can record a fresh baseline.
Dashboard setup remains optional.

If you already use the Philips Skylight integration, the add-on keeps your
existing light, settings and pairing. You do not need to pair again unless
commands are ignored.

## Dashboard controls (optional)

The integration works without creating a dashboard. In the add-on's optional
**Dashboard controls** section, choose **Compact** or **Full**, then either:

- **Create Skylight dashboard** creates a dedicated dashboard, or opens the
  existing one without changing it.
- **Add card to an existing dashboard** lets you choose an editable dashboard
  and view. It adds the Skylight card while preserving the existing controls.

The compact card is intended for a shared dashboard; the full card includes
extra headings and everyday instructions. Both have one power toggle, six modes,
relative dim controls and the separate state-correction view.

For manual setup, download either card configuration and paste it into
**Edit dashboard → Add card → Manual**. Use this route for YAML dashboards or
views the add-on cannot edit. The card uses standard Home Assistant controls;
it requires no HACS or custom dashboard resource and does not register a new
custom type in the card picker. Individual native entities remain available
through **Add card**. See the [dashboard guide](docs/DASHBOARD.md).

## Match the state before first use

**Include this step when you first set up the add-on.** Home Assistant needs an
observed starting state; listening for a power toggle cannot tell whether the
panel started on or off.

1. Look at the physical Skylight. Use **Match recorded state** in the add-on,
   or select **Correct recorded state** at the bottom of the optional card.
2. Select **Panel is on** or **Panel is off** to match what you can see.
3. Select its current mode, or **Mode unknown** if you cannot identify it.
4. In the add-on, select **Record starting state**. On the card, select **Done**
   to return to normal controls.

This records your observation without operating the light. If you pair the
transmitter afterward, repeat state matching after pairing completes.

## Everyday controls

| Control | What it does |
|---|---|
| Power tile | Toggles the physical panel once, like the remote's power button. |
| Mode buttons | Select Refresh, Energize, Focus, Relax, Rest or Auto rhythm. |
| Dim down / Dim up | Dim or brighten by one relative step per tap. |
| Correct recorded state | Opens a separate panel for recording what you can see. |

The recorded mode has a **blue icon**; the other mode icons are gray. This shows
Home Assistant's record, rather than a status reported by the light.

Holding a dashboard dim button does **not** continuously dim the panel. The
receiver recognizes the physical remote's held dim commands. An absolute
brightness slider and color-temperature controls are not available.

## When the state is unknown or incorrect

**Unknown** means Home Assistant needs a starting power state; it does not mean
the light is off. Repeat the state-matching steps above after a restart, pairing,
proxy outage, mains power cycle, or whenever the record no longer matches the
physical panel. Correction only updates Home Assistant's record.

## How state tracking works, and its limits

The Skylight does **not** report its actual power or mode. We estimate those from
commands sent by Home Assistant and BLE button calls received from other
compatible remote/control panels, including commands relayed by light panels.
A received power press flips the known recorded power state; a received mode
press records that mode. Duplicate relay packets are filtered to avoid
double-counting a press. Relative dim presses are recognized, but no absolute brightness
level is tracked.

The estimate can drift out of sync:

- **Missed BLE events:** distance, interference or reception loss can hide a
  remote press from the proxy even when the light receives it.
- **Power switches:** a wall switch, mains interruption or power cycle can
  change the panel without sending a BLE command we can observe.
- **Downtime:** Home Assistant or the proxy cannot track presses while offline;
  restarts require a new observed baseline.
- **Ignored commands:** sending a command, or receiving another controller's
  command, does not prove the physical panel accepted it.
- **Other nearby controllers:** compatible calls intended for another panel
  can affect our record; reception does not identify which panel responded.

The displayed state and blue mode icon are therefore **estimates, not physical
confirmation**. State matching corrects the current record, but cannot prevent
future missed events.

### If tracking is unreliable, use commands only

Use the dashboard's **power toggle**, **mode buttons** and **relative dim buttons**
to issue deliberate commands, and check the physical result. You can keep using
these controls while ignoring the recorded power, mode highlight and entity
states. In automations, the equivalent direct actions are `light.toggle` and
`button.press` for the desired mode or dim button.

Avoid making automation decisions from the estimated state or treating it as
proof that a command worked. Standard `light.turn_on` and `light.turn_off` use
the recorded power to decide whether to send a toggle, so a wrong record can
cause a skipped command or an unexpected toggle. A direct toggle always requests
a change; it cannot guarantee a final on/off state without a trustworthy baseline.

## Pair the transmitter on first setup

A new HA transmitter needs pairing before the panel accepts commands. Pairing
was necessary on the tested panel. If this transmitter already operates the
light, keep its existing pairing; normal updates do not require this step:

1. Open **Pair the transmitter on first setup** in the add-on's web UI.
2. Switch the Skylight's mains power off and back on.
3. Confirm that you are ready, then select **Send pairing request** promptly.
4. Wait about ten seconds. The panel should blink. Check the light and the
   original remote afterward, then correct the recorded state.

The original remote continued working on the tested panel. Pairing behavior
may differ on other models and may require pairing the original remote again.
Pairing is never performed automatically.

## Troubleshooting

| Problem | What to check |
|---|---|
| Add-on not listed in the store | Confirm repository access and that an add-on release is published; otherwise use the local installation linked above. |
| No transmitter appears | Install the supplied proxy firmware and wait for the proxy to reconnect. |
| Remote presses do not update the card | Check the proxy's permission to perform Home Assistant actions and its reception range, then correct the recorded state. |
| Card shows Unknown or the wrong power/mode | Use **Correct recorded state** and record the physical panel's current state. |
| Card download reports a missing control | Keep the Skylight's configuration entities enabled in **Settings → Devices & services**. |
| Commands have no physical effect | Check the proxy connection, then try the explicit pairing procedure above. |
| An update asks for a restart | Restart Home Assistant from the add-on's web UI, then correct the recorded state. |

For add-on options, recovery and removal, see the
[full add-on documentation](philips_skylight/DOCS.md). Protocol research,
implementation details and developer instructions are in the separate
[protocol document](docs/PROTOCOL.md).
