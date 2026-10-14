# Philips Skylight add-on

Control your Philips Skylight from Home Assistant: power, the six modes, and
dimming. Your own remote keeps working, and Home Assistant follows its presses.

You need Home Assistant OS or Supervised (2026.6 or newer) and an ESPHome
Bluetooth proxy near the panel. You do not need an MQTT broker, a cloud account
or a custom dashboard card. It was tested with the NatureConnect/BioUp 17.7 ×
25.6 inch panel and an ESP32-C3 proxy.

## Before you start

- The panel accepts at most two remotes, and Home Assistant counts as one. If
  two remotes already control your Skylight, this does not work unless you give
  one up.
- If you set this up before on another Home Assistant, use **Unpair all
  remotes** first, then pair your remote again.
- One step needs the panel's power switched off and on at its light switch or
  breaker. Use a phone or a portable computer for setup.
- Optional: give the Bluetooth proxy's ESPHome API an encryption key. Without
  one, any device on your home network can make the proxy control the panel.

## Get started

1. Install and start the add-on, turn on **Start on boot**, and open its web page.
2. If the page asks you to restart Home Assistant, select **Restart Home
   Assistant**.
3. Follow the setup checklist. Each step gets a ✓ when it is done.
   1. **Prepare your Bluetooth proxy.** The step checks for ESPHome Device
      Builder, a Bluetooth proxy in it, and Home Assistant's connection to that
      proxy, and says how to fix anything missing. Select **Add Skylight firmware**, then
      install it in ESPHome Device Builder: **⋮ → Install → Wirelessly**.
   2. **Connect Home Assistant to the proxy.** With one proxy, this happens by
      itself.
   3. **Let Home Assistant hear your remote.** Select **Allow**.
   4. **Pair Home Assistant with the panel.** Switch the panel's power off at
      its light switch or breaker, then on again. When the panel is back on,
      select **Pair** straight away. The panel blinks. Then test it and choose a
      mode.
4. Optional: add the Skylight card to a dashboard.

To update, update the add-on in **Settings → Apps**, then open its page. A
**Needs attention** section lists any step left: a Home Assistant restart, new
proxy firmware, or a newer card. It shows only the steps that apply.

## Use the card

The card uses the remote's icons and colors.

- The large **Skylight** tile toggles the power. While the panel is on, it
  glows in the color of the recorded mode.
- A mode button selects that mode and switches the panel on. The recorded mode
  lights up in the remote's color.
- **Dim −** and **Dim +** dim by one step. On a dashboard, a hold dims for
  about 3 seconds after you let go. Keep your finger still, or Home Assistant
  cancels the hold. On the add-on page, holding keeps dimming until you let go.
  You cannot set a brightness level, because the panel takes only these two
  commands.
- **Rhythm set** makes the current time the start of the Auto rhythm schedule.
- **Correct** fixes Home Assistant's record when it does not match the panel.

## The shown state is a best guess

The panel never reports its state. Home Assistant guesses it from its own
commands and the remote presses it hears. A missed press, a power cut or a wall
switch puts the guess out of step. Then use **Correct**.

Leave the panel's wall switch on, and control the panel with its remotes or Home
Assistant. Use the wall switch or breaker only for pairing.

## Pairing and unpairing

Pairing is a one-time step. Updates do not need it, and your remote stays
paired. Pairing Home Assistant again can make the panel drop your remote, so the
page refuses it after setup.

To start over, use **Settings and fixes → Start over**. It unpairs every remote,
has you pair your remote first, and then pairs Home Assistant through the setup
checklist.

See the **Documentation** tab for options, troubleshooting and recovery.
