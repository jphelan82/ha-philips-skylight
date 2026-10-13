# Philips Skylight add-on

Control your Philips Skylight from Home Assistant: power, the six modes, and
dimming. Your own remote keeps working, and Home Assistant follows its presses.

You need Home Assistant OS or Supervised (2026.6 or newer) and an ESPHome
Bluetooth proxy near the panel. You do not need an MQTT broker, a cloud account
or a custom dashboard card. It was tested with the NatureConnect/BioUp 17.7 ×
25.6 inch panel and an ESP32-C3 proxy.

## Get started

1. Install and start the add-on, turn on **Start on boot**, and open its web page.
2. If the page asks you to restart Home Assistant, select **Restart Home
   Assistant**.
3. Follow the setup checklist. Each step gets a ✓ when it is done.
   1. **Prepare your Bluetooth proxy.** Select **Add Skylight firmware**, then
      install it in ESPHome Device Builder: **⋮ → Install → Wirelessly**.
   2. **Connect Home Assistant to the proxy.** With one proxy, this happens by
      itself.
   3. **Let Home Assistant hear your remote.** Select **Allow**.
   4. **Pair Home Assistant with the panel.** Select **Start pairing**. Within
      90 seconds, switch the panel's power off at its light switch or breaker,
      then on again. The panel blinks. Then test it and choose a mode.
4. Optional: add the Skylight card to a dashboard.

## Use the card

The card follows the remote's layout and icons.

- **Skylight** (⏻) toggles the power.
- A mode button selects that mode and switches the panel on. The recorded mode
  lights up in the remote's color.
- **Dim down** and **Dim up** dim by one step. Hold one to dim for about 3
  seconds. On the add-on page, holding keeps dimming until you let go.
- **Rhythm start** makes the current time the start of the Auto rhythm schedule.
- **Correct state** fixes Home Assistant's record when it does not match the
  panel.

## The shown state is a best guess

The panel never reports its state. Home Assistant guesses it from its own
commands and the remote presses it hears. A missed press, a power cut or a wall
switch puts the guess out of step. Then use **Correct state**.

Leave the panel's wall switch on, and control the panel with its remotes or Home
Assistant. Use the wall switch or breaker only for pairing.

## Pairing and unpairing

Pairing is a one-time step. Updates do not need it, and your other remotes stay
paired. To pair again, use **Settings and fixes → Pair again** on the add-on
page.

To make the panel forget every remote, Home Assistant included, use **Settings →
Devices & services → Philips Skylight → Configure → Unpair all remotes**. Then
pair each remote again.

See the **Documentation** tab for options, troubleshooting and recovery.
