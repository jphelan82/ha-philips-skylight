# Changelog

## 0.2.6

- The pairing step lists the mains power cycle as separate numbered steps.
  The documentation states that no unpair command is known and that removing
  the add-on does not unpair the panel.
- After a lost connection, the add-on tries to reconnect at least every five
  seconds, instead of every 30. After a Core restart it is back sooner.
- Native integration 0.2.5: a pairing or skip request without confirmation,
  an unknown effect and an unknown scene are reported as input errors. The
  REST API now answers HTTP 400 for these, not HTTP 500, and Home Assistant no
  longer logs a traceback. This update needs a Core restart.

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
