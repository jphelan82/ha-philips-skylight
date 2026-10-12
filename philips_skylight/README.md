# Philips Skylight add-on

Use a Home Assistant dashboard to toggle your Philips Skylight, choose one of
six modes, and dim or brighten the panel. Your original remote can still be
used, and received remote presses update Home Assistant's recorded state.

**No MQTT broker, cloud account or custom dashboard card is required.** You need
Home Assistant OS or Supervised (Core 2026.6+) and an ESPHome Bluetooth proxy
with the Skylight advertising firmware. The NatureConnect/BioUp 17.7 × 25.6 inch
panel has been tested with an ESP32-C3 proxy.

## Get started

1. Install and start the add-on, enable **Start on boot**, and open its web UI.
2. Restart Home Assistant if requested to activate the light integration.
3. In **Transmitter setup**, choose the advertising action and **BLE Adv Proxy
   Name** sensor from the same proxy, then save. If your proxy needs updating,
   download the firmware configuration and follow the **Documentation** tab.
4. Enable **Allow the device to perform Home Assistant actions** in the proxy's
   ESPHome integration options so remote presses can be received.
5. Select **Download Home Assistant dashboard card**. In your dashboard, choose
   **Edit dashboard → Add card → Manual**, paste the download, and save.

## Use the card

- Tap the power tile to toggle the light once.
- Choose Refresh, Energize, Focus, Relax, Rest or Auto rhythm. The recorded mode
  is blue; the other icons are gray.
- Tap **Dim down** or **Dim up** for one relative brightness step. Holding a
  dashboard button does not continuously dim the light.

## Correct an unknown or incorrect state

The light does not report its status. After a restart or missed remote press,
select **Correct recorded state** at the bottom of the card. The panel changes
so you can select **Panel is on/off** and the mode you can see. Choose
**Mode unknown** if unsure, then select **Done**.

These choices update Home Assistant's record without changing the light.
Received remote presses then keep the record current.

## If commands are ignored

Open **Pair this transmitter**, cycle the panel's mains power, then confirm and
send the pairing request promptly. The request lasts about ten seconds; the
panel should blink. Check the original remote afterward and correct the
recorded state. Other models may require pairing the original remote again.
Pairing never happens automatically.

See the **Documentation** tab for complete proxy setup, options, troubleshooting
and recovery. Protocol and developer notes are maintained separately in the
repository's [protocol document](https://github.com/jphelan82/ha-philips-skylight/blob/main/docs/PROTOCOL.md).
