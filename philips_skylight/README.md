# Philips Skylight add-on

Use a Home Assistant dashboard to toggle your Philips Skylight, choose one of
six modes, and dim or brighten the panel. Your original remote can still be
used. We listen for BLE presses from other compatible remote/control panels
in range and use those commands to update Home Assistant's recorded state.

**No MQTT broker, cloud account or custom dashboard card is required.** You need
Home Assistant OS or Supervised (Core 2026.6+) and an ESPHome Bluetooth proxy
with the Skylight advertising firmware. The NatureConnect/BioUp 17.7 × 25.6 inch
panel has been tested with an ESP32-C3 proxy.

## Get started

1. Install and start the add-on, enable **Start on boot**, and open its web UI.
2. Restart Home Assistant if requested to activate the light integration.
3. Follow the guided setup. If needed, download the ESPHome local package,
   add its `packages`/`!include` entry to your existing node YAML, and compile
   and install it with ESPHome Device Builder. Preserve Wi-Fi, API, OTA and board
   settings. Choose your **Bluetooth proxy** and save; a sole proxy is preselected.
4. Enable **Allow the device to perform Home Assistant actions** in the proxy's
   ESPHome options so remote presses can be received.
5. **Pair the transmitter on first setup.** Skip this step if the HA transmitter
   already works. Updates do not need pairing again.
   1. Tick the confirmation box.
   2. Switch the panel's mains power off at the wall switch or breaker.
   3. Switch the mains power on again.
   4. Select **Send pairing request** straight away. The panel blinks for
      about ten seconds.
   5. Check the panel and the original remote.
6. **Before first use, match the recorded state to the physical panel.** In
   **Record initial state**, observe and select the power. Optionally press a
   mode button on the existing control panel: the mode dropdown always follows
   received presses. Choosing a mode manually records it immediately; choose
   **Unknown** if unsure. Saving sends no light command
   and keeps the latest received mode. Power still needs an
   observation because its button only toggles. A mode press on the remote
   also records power as on, because a mode turns the panel on.
7. **Optional:** choose Compact or Full, then **Create Skylight dashboard** or
   **Add card to an existing dashboard**. Existing dashboards are preserved.
   No dashboard is required to use the native entities.

The compact and full cards use built-in Home Assistant controls and include a
separate state-correction view. You can also download their configuration and
paste it into **Edit dashboard → Add card → Manual**. Entity IDs are filled in.
This reusable configuration does not register a custom card type in the picker.

## Use the card

- Tap the power tile to toggle the light once.
- Choose Refresh, Energize, Focus, Relax, Rest or Auto rhythm. The recorded mode
  is blue; the other icons are gray.
- Tap **Set auto rhythm start** to make the current time the start of the panel's
  daily schedule. The panel blinks. Auto rhythm does nothing until a start is
  set, on the panel's remote or here.
- Tap **Dim down** or **Dim up** for one relative brightness step. Holding a
  dashboard button does not continuously dim the light.

## Correct an unknown or incorrect state

The light does not report its status. After a restart, outage, power cycle or
missed remote press,
select **Correct recorded state** at the bottom of the card. The panel changes
so you can select **Panel is on/off** and the mode you can see. Choose
**Mode unknown** if unsure, then select **Done**.

These choices update Home Assistant's record without changing the light.
Received remote/control-panel presses then update that record.

## State tracking is an estimate

We track Home Assistant commands and received BLE presses, including relayed
commands. Missed BLE events, wall switches or mains interruptions, Home Assistant
or proxy downtime, ignored commands, and calls from other nearby controllers can
make the recorded power or mode incorrect. A blue icon or entity state does not
confirm what the physical panel is doing. Correcting the state establishes a new
baseline, but does not prevent later reception losses.

If tracking proves unreliable, use the **power toggle**, **mode buttons** and
**relative dim buttons** as direct commands and ignore the displayed entity
states. For automations, use `light.toggle` or `button.press` for the desired
mode/dim button. Avoid state-dependent decisions and `light.turn_on`/`light.turn_off`
when the baseline is unreliable: those on/off actions decide whether to toggle
using the recorded state. A direct toggle cannot guarantee a final on/off state;
observe the physical result. A mode button always leaves the panel on, in that
mode, even if it was off.

## Pairing and recovery

Open **Pair the transmitter on first setup** and tick the confirmation box.
Switch the panel's mains power off, then on again. Select **Send pairing
request** straight away. The request lasts about ten seconds, and the panel
blinks. Afterward, check the original remote and correct the recorded state.
Other models can need the original remote paired again. Pairing never happens
automatically.

To make the panel forget **every** remote, open **Settings → Devices & services →
Philips Skylight → Configure** and choose **Unpair all remotes**. It removes the
original remote, any wall remote and Home Assistant. Afterward, pair each remote
again with its own steps, and pair Home Assistant again with **Pair this
transmitter** in the same dialog. No command removes only one remote.

Removing or reinstalling the add-on does not unpair the panel, because the panel
stores the pairing itself. That leftover pairing does no harm: nothing else
sends as Home Assistant's address.

See the **Documentation** tab for complete proxy setup, options, troubleshooting
and recovery. Protocol and developer notes are maintained separately in the
repository's [protocol document](https://github.com/jphelan82/ha-philips-skylight/blob/main/docs/PROTOCOL.md).
