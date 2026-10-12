# Changelog

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
