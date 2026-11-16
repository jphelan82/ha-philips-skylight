# Philips Skylight add-on

Control your Philips Skylight from Home Assistant: power, the six modes, and
dimming. Your own remote keeps working, and Home Assistant follows its presses.
Home Assistant asks the panel whether it is on or off, so the shown power
matches the real panel.

You need Home Assistant OS or Supervised (2026.6 or newer) and an ESPHome
Bluetooth proxy near the panel. You do not need an MQTT broker, a cloud account
or HACS. The integration includes its own dashboard card. It was tested with the NatureConnect/BioUp 17.7 ×
25.6 inch panel and an ESP32-C3 proxy.

## What's new in 0.7.0

Home Assistant now reads the panel's power. It asks after it starts, 5 seconds
after any toggle, after the proxy reconnects, and once a minute. A wrong power
fixes itself within a minute. The new **Philips Skylight: Refresh power**
action asks at once. The update needs a Home Assistant restart and one browser
reload, and no new firmware or pairing.

Many thanks to roy1uno, who found that the panel answers this question and
sent the first version in pull request 9 on GitHub.

## Before you start

- The panel accepts at most two remotes, and Home Assistant counts as one. If
  two remotes already control your Skylight, this does not work unless you give
  one up.
- If you set this up before on another Home Assistant, use **Unpair all
  remotes** first. Then pair Home Assistant, and then your remote.
- One step needs the panel's power switched off and on at its light switch or
  breaker. Use a phone or a portable computer for setup.
- Optional: give the Bluetooth proxy's ESPHome API an encryption key. Without
  one, any device on your home network can make the proxy control the panel.

## Get started

If you have the prerequisites, the add-on walks you through the setup step by
step. You need Home Assistant OS or Supervised 2026.6 or newer, an ESPHome
Bluetooth proxy near the panel, and ESPHome Device Builder. The steps below
show what to expect.

1. Select **Install**. When it is installed, turn on **Start on boot**, select
   **Start**, then select **Open Web UI**.
2. If the page asks you to restart Home Assistant, select **Restart Home
   Assistant**.
3. Follow the setup checklist. Each step gets a ✓ when it is done.
   1. **Prepare your Bluetooth proxy.** The step checks for ESPHome Device
      Builder, a Bluetooth proxy in it, and Home Assistant's connection to that
      proxy, and says how to fix anything missing. Select **Add Skylight firmware**, then
      install it in ESPHome Device Builder: **⋮ → Install → Wirelessly**. The
      Device Builder window never says that it has finished. Come back to the
      add-on page, which says "The install is complete".
   2. **Connect Home Assistant to the proxy.** With one proxy, this happens by
      itself.
   3. **Let Home Assistant hear your remote.** Select **Allow**.
   4. **Pair Home Assistant with the panel.** Switch the panel's power off at
      its light switch or breaker, then on again. When the panel is back on,
      select **Pair** straight away. The panel blinks. Then test it. Next,
      check that your wall remote still works. If it does not, pair it again:
      switch the panel's power off and on, and hold the remote's power button
      for 10 seconds. Then select **The remote works**, **Skip – my remote is
      already working**, or **I have no remote**. Last, choose a mode.
4. Optional: add the Skylight card to a dashboard. Edit the dashboard, select
   **Add card**, open the **By card** tab, and search for **Philips Skylight**. If the card is not in the
   list, reload the page in your browser.

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
- **Correct** fixes the recorded mode, or the power if the panel cannot
  answer.

## The power is read, the mode is tracked

The panel reports its power when Home Assistant asks, so a wrong power fixes
itself within a minute. The panel does not report its mode. Home Assistant
tracks the mode from its own commands and the remote presses it hears. A
missed press, or a press while Home Assistant or the proxy is down, puts the
recorded mode out of step. Then use **Correct**.

You can use the panel with an ordinary wall switch. While the switch is off, the
panel has no power and cannot answer. Home Assistant keeps showing the last
power, and only the wall switch can switch the panel on. When the power
returns, the panel switches on by itself, and Home Assistant reads that within
a minute. For full control from the remotes and Home Assistant, leave the wall
switch on.

## Pairing and unpairing

Pairing is a one-time step. Updates do not need it. Pairing Home Assistant can
make the panel drop your remote, so the setup checklist has you pair the remote
again right after. For the same reason, the page refuses to pair Home Assistant
a second time.

If your wall remote stops working later, pair the remote again first:
switch the panel's power off and on, then hold the remote's power button for 10
seconds. Home Assistant keeps working.

To pair everything again, use **Settings and fixes → Unpair remotes**. It
unpairs every remote, pairs Home Assistant through the setup checklist, and then
has you pair your remote.

See the **Documentation** tab for options, troubleshooting and recovery.
