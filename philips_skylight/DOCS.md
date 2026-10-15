# Philips Skylight

## Requirements

- Home Assistant OS or Supervised, version 2026.6 or newer.
- An ESPHome Bluetooth proxy near the panel, managed in ESPHome Device Builder,
  with ESPHome 2026.4.5 or newer.
- A Philips Skylight panel. The protocol was tested on the NatureConnect/BioUp
  17.7 × 25.6 inch model with an ESP32-C3 proxy.

You do not need an MQTT broker, a cloud account or a long-lived access token.
Supervisor gives the add-on its Home Assistant access.

## Before you start

- The panel accepts at most two remotes, and Home Assistant counts as one. If
  two remotes already control your Skylight, this does not work unless you give
  one up.
- If you set this up before on another Home Assistant, use **Unpair all
  remotes** first, then pair your remote again. The old setup still holds one of
  the two places.
- One step needs the panel's power switched off and on at its light switch or
  breaker. Use a phone or a portable computer for setup.

## Setup

Open the add-on's web page and follow the checklist. Each step gets a ✓ when it
is done.

1. **Finish installing.** At start, the add-on installs its Skylight
   integration into `custom_components/philips_skylight`. If Home Assistant
   needs a restart to load it, the page shows **Restart Home Assistant**. The
   add-on never restarts Home Assistant by itself.
2. **Prepare your Bluetooth proxy.** The step first checks three things, and
   says how to fix each one that is missing:
   - **ESPHome Device Builder is installed.** The add-on looks for its
     `esphome` folder and its page in Home Assistant.
   - **Device Builder has a Bluetooth proxy.** If Home Assistant sees a
     ready-made proxy that Device Builder does not manage yet, the page asks you
     to adopt it.
   - **Home Assistant is connected to the proxy.** The add-on matches the
     proxy's friendly name with Home Assistant's ESPHome devices. If it cannot
     work out the name, it skips this check.

   The page lists the ESPHome Bluetooth
   proxies in your `esphome` folder. **Add Skylight firmware** does three
   things:
   - It copies `skylight-transmitter.yaml` and `components/ble_adv_proxy` into
     the `esphome` folder. If a different `ble_adv_proxy` component is already
     there, it first saves a copy as `ble_adv_proxy.bak-<time>`.
   - It saves a copy of the proxy's YAML as `<name>.yaml.bak-<time>`.
   - It adds `skylight: !include skylight-transmitter.yaml` under `packages:`.

   Then install the firmware in ESPHome Device Builder: open the proxy, then
   **⋮ → Install → Wirelessly**. The page continues when the proxy is back.

   Device Builder builds the firmware first, on the computer that runs Home
   Assistant. The first build can take up to 15 minutes, and longer if that
   computer is small, such as a Raspberry Pi. Its window never
   says that it has finished. Check the add-on page instead: it says "The install
   is complete" when the proxy is back with the new firmware. In the Device Builder
   log, the install is done when the build messages stop and the proxy's own
   messages scroll by. Each of those starts with the time and a letter, such as
   `[12:00:01.234][D]`. You can close the window then.

   The package turns on the proxy's API actions, scans for Bluetooth all the
   time so that no remote press is missed, and turns off Wi-Fi roaming. A proxy
   on a wall does not need roaming, and each roam breaks the connection to Home
   Assistant for up to 45 seconds.
3. **Connect Home Assistant to the proxy.** With one compatible proxy, the
   add-on sets up the integration by itself. With several, choose one.
4. **Let Home Assistant hear your remote.** **Allow** turns on the proxy's
   setting **Allow the device to perform Home Assistant actions**. The add-on
   changes it through the ESPHome integration's own settings dialog.
5. **Pair Home Assistant with the panel.** See [Pairing](#pairing-and-unpairing).
   Then select **Switch the panel on or off**, and say what the panel did. That
   answer records the real power. Last, choose a mode. A mode switches the panel
   on in that mode, so Home Assistant then knows both.

After setup, the page shows the panel's recorded state, controls, the
dashboard tools, and **Settings and fixes**.

If you already use the Philips Skylight integration, the add-on keeps your
entities, settings and pairing.

## Updates

After an update, a **Needs attention** section on the add-on page lists what still
needs you.

1. **Update the add-on.** Home Assistant offers the update under **Settings →
   Apps**. Select **Update**. The add-on restarts by itself.
2. **Restart Home Assistant, if the page asks.** The add-on installs its copy of
   the integration when it starts. If that copy is new, the page shows
   **Restart Home Assistant**. The add-on never restarts Home Assistant by
   itself.
3. **Update the proxy firmware, if the page asks.** The page compares three
   things: the add-on's firmware files, the copies in your ESPHome folder, and
   the firmware number that the proxy reports.
   - If the copies are older, the page shows **Update the firmware files**. It
     keeps a backup of the old files.
   - Then, or if the proxy reports an older number, the page asks you to
     install: in ESPHome Device Builder, open the proxy, then **⋮ → Install →
     Wirelessly**. The proxy is offline for a minute or two, and Home Assistant
     misses remote presses in that time.
   - If the firmware did not change, the page shows nothing.
4. **Update the card, if the page asks.** A card on a dashboard never changes
   by itself. If a dashboard holds an older Skylight card, the page shows
   **Update the card**. It replaces only the Skylight card and leaves the rest
   of the dashboard as it is.

The page shows a step only when its part changed. An update never needs a new
pairing, and it keeps your settings and the command counter.

Firmware updates cover proxies whose YAML includes
`skylight: !include skylight-transmitter.yaml`, which is what **Add Skylight
firmware** sets up. A proxy with the Skylight parts written straight into its
YAML gets no firmware steps on the page. Replace those parts with the package
line to get them.

The proxy reports its firmware number as the **Skylight firmware** diagnostic
sensor. Firmware from before add-on 0.4.0 has no number, so the page asks for
one install after the update to 0.4.0.

The add-on finds its card by its shape: a vertical stack that ends with the
controls and the correction view of the state correction switch. It reads every
editable dashboard, the default one included, when you open the page, and at
most every 5 minutes after that.

## Pairing and unpairing

The panel accepts a pairing request only for a short time after it comes back on.

1. Switch the panel's power off at its light switch or breaker, then on again.
   The remote's power button does not work for this.
2. Wait until the panel is back on. That can take up to 30 seconds.
3. Select **Pair** straight away. Home Assistant sends the request for 10
   seconds, and the panel blinks.

Home Assistant sends a short burst, like the remote's own 10-second hold. A long
stream of requests makes the panel drop your remote. Your remote stays paired.
Pairing never happens by itself.

If your wall remote stops working after Home Assistant pairs, pair the remote
again first: switch the panel's power off and on, wait until it is back on, then
hold the remote's power button for 10 seconds. Home Assistant keeps working. Use
**Start over** only if that does not help.

Pair Home Assistant only once. Pairing it again can make the panel drop your
remote, so the add-on page refuses it after setup. To pair again, use **Settings
and fixes → Start over** on the add-on page. It unpairs every remote, has you
pair your remote first, and then pairs Home Assistant through the setup
checklist.

**Configure** on the Skylight integration also offers **Pair this transmitter**
and **Unpair all remotes**, with the same steps. Use **Pair this transmitter**
only when Home Assistant is not paired yet, for example after **Unpair all
remotes**. **Unpair all remotes** makes the
panel forget every remote, Home Assistant included. If its request reaches the
panel too late, the panel only switches off. Then try again. Afterward, pair your
remote again.

Removing the add-on does not unpair the panel. The leftover pairing does no
harm, because nothing else sends as Home Assistant's address.

## The Skylight card

**Create a Skylight dashboard** or **Add to a dashboard** places the card. The
add-on uses Home Assistant's dashboard API. It checks the dashboard's version
before it adds the card, and it does not add the same card twice. For YAML
dashboards, generated dashboards and panel views, use **Download the card
instead** and paste it into **Edit dashboard → Add card → Manual**. The card
uses only built-in Home Assistant cards.

The card uses the remote's icons and colors:

- The large **Skylight** tile toggles the power and shows the recorded power
  and mode. While the panel is on, it glows in the recorded mode's color.
- Six mode buttons. The recorded mode lights up in the remote's color.
- **Dim −** and **Dim +**. A tap is one step. A hold sends the remote's hold
  command for about 3 seconds. Home Assistant sends it when you let go, not
  while you hold, and it cancels the hold if your finger moves. A circle shows
  when a press counts as a hold. On the add-on page, holding a dim button keeps
  dimming until you let go.
- **Rhythm set** sets the current time as the start of the Auto rhythm
  schedule, like holding Auto rhythm and Relax on the remote.
- **Correct** switches the card to **Panel is on**, **Panel is off**, the
  six modes and **Mode unknown**. These change only Home Assistant's record.
  **Done** returns to the controls.

## The recorded state

The panel never reports its state. Home Assistant records the power and mode from
its own commands and from the remote presses it hears through the proxy. Each
remote press updates the record. A mode press also records the power as on.
Home Assistant never sends a command because of a received press.

The record goes wrong after a missed press, a power cut, a wall switch, or a
proxy or Home Assistant outage. A proxy reconnect within 60 seconds keeps the
record. A longer outage clears it. Then use **Correct** on the card.

Leave the wall switch on. Control the panel with its remotes or Home Assistant.
If the panel's power runs through a smart switch in Home Assistant, an
automation can follow it with the `philips_skylight.set_assumed_power` action.
That action sets the shown power and sends nothing to the panel. When power
returns, the panel switches on by itself, so the switch's state is the panel's
power. The README has an example.

You cannot set a brightness level. The panel takes only "dim down" and "dim
up" commands and never reports its level. Home Assistant ignores a brightness
in `light.turn_on`.

For automations, send commands that do not depend on the record:
`light.toggle`, `button.press` on a mode button, and `philips_skylight.dim`.
`light.turn_on` and `light.turn_off` decide from the recorded power, so they do
the wrong thing when the record is wrong. `light.turn_on` with an effect always
sends that mode.

## Options and permissions

- **Install the companion integration:** installs or updates the bundled
  integration at start. Turn it off if you manage the integration by hand or
  with HACS. A newer installed version is never replaced.
- **Log level:** debug, info, warning or error.

The add-on needs the Home Assistant API and write access to the configuration
folder. It writes only to `custom_components/philips_skylight` and, when you
select **Add Skylight firmware**, to the `esphome` folder, always with backups.
It never edits `configuration.yaml`, `.storage` or credentials. Its own backups
of older integration code live in the add-on's `/data` folder, which Supervisor
backups include.

The web page is open only through Home Assistant's ingress. No port is exposed.
A Docker health check inside the container reads only the `/health` page. The
page takes its colors from the Home Assistant theme you have open.

### The proxy

- **An API encryption key for the proxy is optional.** Without one, any
  device on your home network can connect to the proxy and make it send
  commands to the panel. The add-on page notes, as optional, when a proxy that
  runs the Skylight firmware has no key in its YAML.
- **Allow the device to perform Home Assistant actions** lets the proxy report
  remote presses. The same setting lets the proxy call any Home Assistant
  action. The Skylight firmware only sends press events, but the setting trusts
  everything that runs on the proxy. Install only firmware you trust on it.
- The firmware forwards only Bluetooth mesh messages to Home Assistant.
  Adverts from phones, watches and other nearby devices stay on the proxy, so
  Home Assistant's recorder never stores them. Firmware before version 2
  forwarded every advert it heard.

## Recovery and removal

To remove everything, delete the Philips Skylight integration in **Devices &
services**, then uninstall the add-on. Keep the integration's command counter
file, `.storage/philips_skylight.sequence_7ffe`. Home Assistant needs it if it
pairs with the panel again later.

The panel ignores a command whose counter number is not higher than the last
one it accepted. After a Home Assistant rebuild without a backup, or a restore
from an older backup, the counter is too low. Use **Settings and fixes → The
panel ignores Home Assistant after a backup restore**. It moves the counter
forward by about one million and sends nothing to the panel. Each use spends
one sixteenth of the counter's range, so use it only for this problem.

If an update fails, the previous integration code is in `/data/backups`. Restore
only that code, then restart Home Assistant. If an update was cut off, the
folder `custom_components/.philips_skylight-previous` can remain. Recover it,
and keep the counter file.

To undo the firmware change, restore the proxy's `.bak-<time>` YAML, then
install it again in ESPHome Device Builder. Restoring the YAML alone does not
change the firmware on the proxy.
