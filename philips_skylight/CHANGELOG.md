# Changelog

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
