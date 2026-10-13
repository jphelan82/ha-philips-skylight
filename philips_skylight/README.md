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
5. **Pair the transmitter on first setup.** Cycle the panel's mains power, then
   confirm and send the pairing request promptly. Check the panel and original
   remote. Skip this step if the HA transmitter already works; updates do not
   require re-pairing.
6. **Before first use, match the recorded state to the physical panel.** In
   **Match recorded state**, record the power and mode you can see, or
   **Unknown** for the mode. This records observations without operating the light.
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
observe the physical result.

## Pairing and recovery

Open **Pair the transmitter on first setup**, cycle the panel's mains power, then confirm and
send the pairing request promptly. The request lasts about ten seconds; the
panel should blink. Check the original remote afterward and correct the
recorded state. Other models may require pairing the original remote again.
Pairing never happens automatically.

See the **Documentation** tab for complete proxy setup, options, troubleshooting
and recovery. Protocol and developer notes are maintained separately in the
repository's [protocol document](https://github.com/jphelan82/ha-philips-skylight/blob/main/docs/PROTOCOL.md).
