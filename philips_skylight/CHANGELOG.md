# Changelog

## 0.5.0

A review of all the code found the problems below. This version fixes them.
It needs a Home Assistant restart for integration 0.4.0, and an install of
Skylight firmware 3 on the proxy.

**Setup and pairing**

- A page reload during setup no longer offers **Pair** again after Home
  Assistant paired. The add-on remembers the pairing and refuses a second one.
  After **Nothing changed**, **Pair** opens again.
- The remote step after pairing has a **Skip – my remote is already working**
  button on a first install. After **Unpair remotes**, the step says that the
  remote was unpaired too, and it has no Skip button.
- With one proxy, the checklist shows a **Connect** button. Before, a failed
  automatic connect left "Connecting…" with no way forward.
- **Add Skylight firmware** works for a proxy that Home Assistant lists only as
  a Bluetooth scanner.
- **Unpair remotes** shows each message next to its own step.
- The tracking step says that it is optional.

**Reliability**

- The add-on reconnects after Home Assistant closes the connection at any
  point. Before, a restart at the wrong moment left it on "Connecting" until
  the add-on restarted.
- An install error at startup no longer stops the add-on. The page shows it.
- The restart notice clears when Home Assistant runs the new integration.
- After an add-on update, buttons say "The add-on restarted. Reload this page."
  An error from a failed status check clears when the next check works.
- Card updates skip dashboards in YAML mode. One failed dashboard does not stop
  the others.
- A README change to the firmware component no longer asks for a firmware
  update.
- A proxy YAML with a `packages:` list gets a clear message, and the add-on
  writes nothing to it.

**Integration 0.4.0**

- **Configure → Pair this transmitter**, **Unpair all remotes** and the pairing
  actions report an error when the proxy is offline. Before, they reported
  success and sent nothing.
- `set_assumed_power` and `skip_sequence` work while the proxy is offline. So
  do **Record panel on**, **Record panel off** and **Recorded scene**.
- `light.toggle` with an effect sends that mode.
- Remote tracking and outage handling no longer depend on the light entity.
- Unload and reload stop dim holds and pairing bursts.
- A second pairing burst no longer loses its countdown when the first ends.

**Skylight firmware 3**

- The proxy uses its highest transmit power. On an ESP32-C3, that is +20 dBm.
  Before, a preprocessor mistake set every chip to +9 dBm.
- If the Bluetooth stack drops an event, the proxy gives up on that packet after
  one second. Before, it stopped sending until a reboot.

**Page**

- Hold-to-dim ignores a cancelled touch, other mouse buttons and a second
  finger. It stops when the page loses focus.
- Keyboard focus stays on the control that you used.
- Arrow keys on the mode list send only the final choice.

**Releases**

- The release workflow runs all tests before it publishes images.

## 0.4.24

- The setup checklist warns at the top that setup can unpair your wall remote,
  and that its last step has you pair the remote again.

## 0.4.23

- Setup pairs Home Assistant first and the wall remote second. On 2026-10-15,
  pairing Home Assistant after the remote made the panel drop the remote twice.
  Pairing the remote after Home Assistant kept both working, both times.
- The setup checklist has a new step after the test: pair your wall remote
  again. Select **The remote works**, or **I have no remote**.
- **Unpair remotes** hands over to the setup checklist after the unpair. The
  checklist pairs Home Assistant, then has you pair your remote.
- Integration 0.3.4: **Configure → Pair this transmitter**, **Unpair all
  remotes** and the pairing action describe the same order. This update needs a
  Home Assistant restart.

## 0.4.22

- **Settings and fixes → Start over** is now called **Unpair remotes**.
- The separate **Unpair all remotes** section on the add-on page is gone. It
  only pointed to **Start over**.

## 0.4.21

- **Start over** is a numbered list of three steps, like the setup checklist.
  Each step has its own button, and only the current step's buttons work:
  1. Switch the power off and on, then select **Unpair all**. The checkbox now
     says "The panel just came back on".
  2. Say whether the panel blinked. If it did not, the page goes back to step 1.
  3. Pair your remote, then select **Continue**.
- The 0.4.20 changes reach users with this version.

## 0.4.20

- **Start over** shows its messages under its own buttons. Before, the result
  of **Unpair all** showed only in the notice bar at the top of the page, out
  of view, so the button seemed to do nothing.
- While an unpair runs, the countdown shows under **Unpair all** and says
  "Unpairing". Before, a countdown at the top of the page said "Pairing".
- When the unpair finishes, the page says what to do next.
- **Tick the box first** shows next to the button that needs the box.

## 0.4.19

- **Settings and fixes → Start over** and the docs now say to pair the wall
  remote again first if it stops working after setup. Switch the panel's power
  off and on, then hold the remote's power button for 10 seconds. Home
  Assistant keeps working. Use **Start over** only if that does not help.

## 0.4.18

- Integration 0.3.3: pairing and **Unpair all** send their request twice a
  second for 10 seconds, like the remote's own pairing hold. Before, Home
  Assistant sent three a second. On 2026-10-15, a pairing at three a second
  made the panel drop the wall remote. This update needs a Home Assistant
  restart.

## 0.4.17

- **Add to a dashboard** puts the card in a new section when the view has
  sections but names no view type. Home Assistant shows such a view as a
  sections view. Before, the card went into the view's old card list, which
  shows only while you edit the dashboard.
- The result of **Create a Skylight dashboard** and **Add the card** shows right
  under the buttons, as well as in the notice bar at the top.
- The install guidance says that Device Builder builds the firmware on the
  computer that runs Home Assistant.

## 0.4.16

- When a proxy already has the Skylight firmware files but no install yet, the
  first setup step shows only the install instruction for that proxy. Before,
  it also listed the other proxies, which suggested a choice was still open.

## 0.4.15

- **Open ESPHome Device Builder** is larger and sits right under the install
  instruction, above the longer guidance about build times.

## 0.4.14

- **Open ESPHome Device Builder** and the setup checks' links open in a new
  tab. The add-on page stays open, so you can come back to it to see that an
  install is complete.

## 0.4.13

- The setup page finds Bluetooth proxies that run ready-made firmware, such as
  the Apollo MSR-2. Their YAML turns the proxy on in a package from GitHub, so
  it has no `bluetooth_proxy:` section. The add-on now also asks Home Assistant
  which ESPHome devices it uses as Bluetooth proxies.
- The page names a proxy by its friendly name, as Device Builder and Home
  Assistant do, with its device name after it: "bluetooth-proxy-1
  (esphome-web-ece638)".
- The **Proxy offline** badge waits until a proxy has the Skylight firmware.
  Before that, it read like a fault.

## 0.4.12

- While Home Assistant restarts, the add-on page says so below **Restart Home
  Assistant**: "Home Assistant is restarting. That can take a few minutes."
  This also works for a restart started from Home Assistant's own menu.
- During the restart, the page shows no errors for requests that fail because
  Home Assistant is down. When Home Assistant is back, the page says "Home
  Assistant has restarted."

## 0.4.11

- **Restart Home Assistant** on the add-on page works again. While a restart was
  pending, the page greyed out every button, this one included.
- Greyed-out buttons show a "not allowed" pointer instead of a busy one.
- The install steps name the buttons in order: **Open link**, **Add**,
  **Install**, **Start** and **Open Web UI**.

## 0.4.10

- The install guidance says that the first firmware build can take up to 15
  minutes. A full rebuild took 13 minutes on the test system.
- The example log line shows the real format, with milliseconds:
  `[12:00:01.234][D]`.

## 0.4.9

- Clearer guidance on when a firmware install is done. The add-on page is the
  main sign. `OTA successful` scrolls out of view in seconds, so the page no
  longer points to it.

## 0.4.8

- The page explains how to tell that a firmware install in ESPHome Device
  Builder is done. Device Builder's window never says so. The page does, and in
  the log, the build messages stop and the proxy's own messages scroll by. The
  first build takes several minutes.
- The page says when the proxy is back with the new firmware: "The install is
  complete."

## 0.4.7

- Without ESPHome Device Builder, the first setup step also offers the firmware
  package as a download, for building it with your own ESPHome. Device Builder
  stays the recommended way.

## 0.4.6

- The first setup step starts with three checks: ESPHome Device Builder is
  installed, Device Builder has a Bluetooth proxy, and Home Assistant is
  connected to that proxy. Each missing item says how to fix it, with a link:
  the app store for Device Builder, ESPHome's ready-made projects for a new
  proxy, or Home Assistant's ESPHome devices for one that is not added yet.
- If Home Assistant sees a ready-made proxy that Device Builder does not manage
  yet, the page asks you to adopt it in Device Builder.
- Proxy names written with `${...}` substitutions now show their real names.

## 0.4.5

- The add-on comes as a prebuilt image for amd64 and aarch64. Home Assistant
  downloads it instead of building the add-on on your machine, so installs and
  updates take seconds, and they no longer depend on a package download during
  the build.
- Each version has a GitHub release with its changelog.

## 0.4.4

- Holding a dim button on the add-on page sends a hold command every 0.6
  seconds again, like the remote. Before, each command waited for the one
  before it to finish, so there were pauses of about 1.3 seconds or more.
- The add-on answers a hold request at once and sends the command in the
  background. At most two hold commands wait at a time, so a slow connection
  cannot keep the panel dimming after you let go.

## 0.4.3

- Holding **Dim −** or **Dim +** on the dashboard card works from the tile's
  icon too. A tile card gives its icon separate actions, and the card set the
  hold only for the rest of the tile. On a phone the thumb lands on the icon,
  so a hold did nothing there.
- After this update, the add-on page offers **Update the card** for cards
  added before 0.4.3.

## 0.4.2

- Holding **Dim −** or **Dim +** on the add-on page works on a phone. Before,
  the phone opened its own menu after about half a second and cancelled the
  touch, so the hold stopped. The button now keeps the touch until the finger
  lifts, even if it slides a little.

## 0.4.1

- The API key note on the add-on page is marked optional. If it is the only
  item, the section heading reads **Needs attention (optional)**. The docs call
  the key optional too.

## 0.4.0

- The add-on page has a **Needs attention** section. It shows only the steps
  that an update needs: new firmware files, a firmware install on the proxy, or
  a newer dashboard card.
- The firmware package has a version number, now 2. The proxy reports it as the
  **Skylight firmware** diagnostic sensor. Firmware from before this version
  reports no number, so the page asks for one install in ESPHome Device
  Builder after this update.
- **Update the firmware files** copies the new firmware files into the ESPHome
  folder and keeps backups of the old ones. It does not change the proxy's own
  YAML.
- **Update the card** replaces older Skylight cards on every editable
  dashboard, the default one included. It changes nothing else on a dashboard.
- With firmware 2, the proxy forwards only Bluetooth mesh messages to Home
  Assistant. Older firmware forwarded every Bluetooth advert in range, so Home
  Assistant's recorder stored the addresses of nearby phones, watches and other
  devices.
- The page notes, as optional, when a proxy with the Skylight firmware has no
  ESPHome API encryption key. Without one, any device on the home network can make the
  proxy control the panel.
- The page takes its colors, font and shapes from the open Home Assistant
  theme, custom themes and dark mode included.
- The add-on's sidebar icon is the flat ceiling light, like the light entity.
- The docs no longer show the test home's device addresses, host name or IP
  address.
- The integration is unchanged, so this update needs no Home Assistant restart.

## 0.3.3

- Native integration 0.3.2: **Configure → Pair this transmitter** and the
  `philips_skylight.pair_transmitter` action warn to pair Home Assistant only
  once, and explain why: a second pairing can make the panel drop your remote.
  This update needs a Home Assistant restart.
- A new look for the Skylight card. The large **Skylight** tile at the top
  glows in the recorded mode's color while the panel is on. A mode tile lights
  up only while the panel is on. **Correct**,
  **Rhythm set**, **Dim −** and **Dim +** share one row of small icon tiles, with
  the dim tiles on the right for a right thumb. The help line is gone.
- The Skylight light, its card tile and the Skylight dashboard use the flat
  ceiling light icon, `mdi:wall-sconce-flat`.
- The card has one size. The **Compact** and **Full** choice is gone, and so is
  `skylight-card-compact.yaml`. A card you added before keeps working. To get
  the new look, delete the old card and add it again.
- The docs say that you cannot set a brightness level. The panel takes only
  "dim down" and "dim up" commands.

## 0.3.2

- After setup, the add-on page refuses to pair Home Assistant again, because a
  second pairing can make the panel drop your remote.
- **Settings and fixes → Pair again** is now **Start over**. It unpairs every
  remote, has you pair your remote first, and then reopens the setup checklist
  to pair Home Assistant and run the tests.
- The integration is unchanged, so this update needs no Home Assistant restart.

## 0.3.1

- Pairing and **Unpair all remotes** send one 10-second burst again, like the
  remote's own hold. The 90-second stream of 0.3.0 made the panel drop the
  other remote. Switch the panel's power off and on, wait until it is back on,
  then select **Pair** straight away.
- The **Done** and **Stop** buttons and the `philips_skylight.stop_pairing`
  action are gone. The `duration` option of the pairing actions is gone too.
- The setup page and the docs say up front that the panel accepts at most two
  remotes, Home Assistant included. If you set this up before on another Home
  Assistant, use **Unpair all remotes** first.
- The setup page says at the start that one step needs the panel's power
  switched off and on, so you can use a phone or a portable computer.
- Native integration 0.3.1 needs a Home Assistant restart.

## 0.3.0

Setup
- The add-on page is a setup checklist. Each step gets a ✓ when it is done.
- **Add Skylight firmware** copies the firmware package into your ESPHome
  folder and adds its line to the proxy's YAML, with a backup of each file.
  You then install it in ESPHome Device Builder with one click.
- With one compatible proxy, the add-on connects it without asking.
- **Allow** turns on the proxy's remote tracking setting. The page shows
  whether it is on.
- Pairing uses a 90-second window, with **Done** to end it early. The
  integration's **Configure** dialog and **Unpair all remotes** use the same
  window, and the dialog no longer freezes. Version 0.3.1 replaces the window,
  because it made the panel drop the other remote.
- After pairing, a power toggle tests it, and your answer records the real
  power. Then you choose a mode, so Home Assistant knows the mode too.
- After setup, the page shows the recorded state, controls and a short
  **Settings and fixes** list. The page follows the device's dark mode.

Cards and controls
- The card follows the remote's layout: the power tile, then Auto rhythm,
  Refresh, Energize, Focus, Relax and Rest, then dimming. Each control uses the
  remote's icon, and the recorded mode lights up in the remote's dot color.
  **Rhythm start** and **Correct state** share one row.
- Press-and-hold dimming. On the add-on page, holding a dim button sends the
  remote's hold command every 0.6 seconds until you let go. On a card, a hold
  dims for about 3 seconds. The new `philips_skylight.dim` action takes a
  direction and an optional hold time.
- The integration's buttons use the same icons as the card.

Reliability
- A proxy reconnect within 60 seconds keeps the recorded power and mode. A
  longer outage still clears them.
- Firmware package: `wifi: post_connect_roaming: false`. ESPHome's roaming scan
  every five minutes switched the tested proxy between access points all day.
  Each switch broke the Home Assistant connection for up to about 45 seconds,
  and commands sent then were lost. Install the updated firmware on the proxy.

Native integration 0.3.0 needs a Home Assistant restart.

## 0.2.8

- Native integration 0.2.7: **Configure** on the integration offers **Pair
  this transmitter** and **Unpair all remotes**. Each one explains the power
  cycle first and needs a tick box. This update needs a Core restart.
- Unpair all remotes makes the panel forget every paired sender: the original
  remote, wall remotes and Home Assistant. Afterward each one needs pairing
  again. The `philips_skylight.unpair_all_remotes` action does the same for
  scripts.
- `tools/capture.py` warns against running more than one copy.

## 0.2.7

- Native integration 0.2.6: the pairing and skip actions require `confirm:
  true` in their schema. A call without it fails validation before any code
  runs. The REST API then answers HTTP 400 instead of HTTP 500, and Home
  Assistant logs no traceback. This update needs a Core restart.
- New **Set auto rhythm start** button and card tile. It sends the command
  that the remote sends when Auto rhythm and Relax are held together. The
  panel takes the current time as the start of its daily schedule. Received
  presses of that combination are recognized too. Auto rhythm stays a mode.
- `tools/capture.py` records remote commands through the proxy's ESPHome API.
  It only listens.

## 0.2.6

- The pairing step lists the mains power cycle as separate numbered steps.
  The documentation states that no unpair command is known and that removing
  the add-on does not unpair the panel.
- After a lost connection, the add-on tries to reconnect at least every five
  seconds, instead of every 30. After a Core restart, Supervisor accepts the
  connection only when Core reaches its running state. The add-on now connects
  within five seconds of that.
- Native integration 0.2.5: a pairing or skip request without confirmation,
  an unknown effect and an unknown scene are reported as input errors. The
  Home Assistant frontend shows them as user errors. This update needs a Core
  restart.
- Native integration 0.2.5: a mode command turns an off panel on, in that
  mode. After any mode command, sent from Home Assistant or received from a
  remote, the integration records power as on. `light.turn_on` with an effect
  sends only the mode command, and it works while power is unknown.

## 0.2.5

- New recovery control: **Skip sequence forward**. Use it if the panel ignores
  the transmitter after Home Assistant was rebuilt without a backup or restored
  from an older backup. It needs confirmation, sends no light command and does
  not need pairing again. The integration adds the matching
  `philips_skylight.skip_sequence` action.
- The add-on follows only the Skylight entities and ESPHome sensors, instead of
  every state change in Home Assistant. The status page no longer repeats the
  proxy search for every sensor on each two-second refresh.
- Firmware: duplicate-packet timers keep working after the proxy's 49-day
  `millis()` rollover. The runtime patch of ESPHome's `api` schema is removed.
  The package YAML already sets both options.
- Native integration 0.2.4: stores its controller in `entry.runtime_data` and
  uses current Home Assistant import paths. This update needs a Core restart.

## 0.2.4

- Guided setup shows relevant steps, with completed installation settings
  collapsed under Setup and recovery. One matched proxy selector, an advanced fallback, explicit
  first-time pairing, remote-tracking permission instructions and initial state matching.
- Record initial state's mode dropdown follows received control-panel presses.
  Manual mode choices record immediately without sending a light command.
  Power still requires an observed baseline.
- Downloadable ESPHome local package, added with one packages/include entry.
- Optional dashboard creation or additive card installation into an existing
  editable dashboard view through Home Assistant's native API.
- Compact and full reusable cards using standard controls, including selected
  mode colors and a separate correction view. Dashboard setup is not required.
- Existing dashboards are preserved; stale edits and duplicate cards are rejected.
- Native integration remains at 0.2.3; this add-on update needs no Core restart.

## 0.2.3

- One power toggle on the dashboard, matching the verified BLE power command.
- Selected mode icons are blue; other mode icons are gray.
- Correct recorded state opens a separate panel where power and mode choices
  record observations without sending commands. Done restores normal controls.
- Native State correction switch controls the view and resets off after reload.

## 0.2.2

- Native state correction entities: Record panel on/off buttons and a Recorded
  scene selector. These update assumed state without transmitting BLE commands.
- Reusable Skylight dashboard card built from standard Home Assistant controls.
- Download a card with the installation's actual entity IDs, including renames.
- Expose the recorded scene even while power is off or unknown.

## 0.2.1

- Track power, scene selection and the last dim command from compatible external
  remote senders, rather than only the original remote's fixed Mesh address.
- Deduplicate rapid transaction repeats per sender, including interleaved
  remotes and buttons; ignore our own commands returning through panel relays.
- Preserve unknown power until synchronized and keep dimming relative.

## 0.2.0

- Supervisor add-on for amd64 and aarch64, with protected Home Assistant ingress.
- Native light integration installation and updates with code backups.
- Transmitter setup and reconfiguration without changing entity IDs or mesh storage.
- Power, six scenes, relative dimming, explicit power synchronization and pairing.
- Native API reconnects with no automatic replay of control requests.
- Downloadable ESPHome advertising firmware configuration.
- No MQTT or cloud dependency; no host networking or privileged hardware access.
