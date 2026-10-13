# Changelog

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
