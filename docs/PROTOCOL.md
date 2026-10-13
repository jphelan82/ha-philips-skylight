# Philips Skylight: Bluetooth Mesh protocol

This document contains protocol research, implementation notes and developer
instructions moved out of the README files. For installation and everyday use,
start with the [end-user README](../README.md).

The skylight is a Philips LED Skylight Ceiling Panel (NatureConnect, BioUp, 17.7 x 25.6 in). Philips sells it as remote-only: no app, no Hue, no Matter, no Wi-Fi. Inside, it runs standard Bluetooth Mesh, and its remote uses factory-default keys. This file records what we decoded on 2026-10-12, so Home Assistant can send the same commands as the remote.

## The hardware

| Part | What we found |
|---|---|
| Panel radio | Bluetooth Low Energy (BLE) Mesh module, address `4C:3C:8F:EA:96:76`. The address prefix belongs to Shenzhen Jingxun Technology. The panel advertises the name `BK_MESH_light`, which points to a Beken chip. |
| Panel beacon | The panel always sends the "unprovisioned device" beacon (service `0x1827`), even after pairing. Ignore it. The panel is on the default network from the start, and it relays the remote's packets. |
| Remote | A battery mesh node. It sends from mesh address `0x7FFF` to `0xFFFF` (all nodes). Its BLE address for the proxy advert is `F6:E2:99:FE:DE:B1`. The ESPHome proxy reports its command packets under `FF:FF:FF:FF:FF:FF`. |
| FCC ID | `2AGBW929004709X`, 2402 to 2480 MHz. |

## The keys

Both keys are factory defaults. Every unit of this model very likely uses the same pair.

| Key | Value | How we know |
|---|---|---|
| Network key (NetKey) | `11111111111111111111111111111111` | The remote's 64-bit network ID is `c7cd5342d1544cd5`. The mesh function k3 of this key gives exactly that ID. |
| Application key (AppKey) | `00000000000000000000000000000000` | Its 6-bit key ID matches (`0x38`), and it decrypts every captured command with a valid message check. |
| IV index | `0` | From the remote's secure network beacon. |

## The commands

Each command is a vendor message with company ID `0x0211` (Telink Semiconductor). The bytes below are the decrypted access payload. `TT` is a transaction number. The remote counts it up by one per press, from `0x80` to `0xFF`, and then wraps back to `0x80`.

| Button | Payload | Notes |
|---|---|---|
| On/off | `C8 11 02 TT 03 01 41` | A toggle. We have not found separate on and off codes yet. |
| Dim down, tap | `C8 11 02 TT 01 00 14 41` | `0x14` is 20, likely a 20 percent step. |
| Dim up, tap | `C8 11 02 TT 01 01 14 41` | |
| Dim down, hold | `C8 11 02 TT 01 02 14 41` | The remote repeats it about every 0.6 s while held. |
| Dim up, hold | `C8 11 02 TT 01 03 14 41` | Same repeat as dim down. |
| Refresh | `C9 11 02 TT 04 FF 01 41` | `C9` is the scene command. |
| Energize | `C9 11 02 TT 04 FF 02 41` | |
| Focus | `C9 11 02 TT 04 FF 03 41` | |
| Relax | `C9 11 02 TT 04 FF 04 41` | |
| Rest | `C9 11 02 TT 04 FF 05 41` | |
| Auto rhythm | `C9 11 02 TT 04 FF 06 41` | |
| Pair (hold on/off 10 s after power-on) | `CF 11 02 TT 01 11 11 11 11 11 11` | Sent about three times a second for the whole hold. Six `11` parameter bytes follow `01`; the complete access payload is 11 bytes. |

Every command ends in `0x41`. Its meaning is unknown.

## Rules for sending from Home Assistant

- **Never send as the remote's address `0x7FFF`.**
  A mesh node drops any packet whose sequence number is not higher than the last one from the same sender. If Home Assistant sends as `0x7FFF` with a high sequence number, the panel ignores the real remote until the remote catches up. Use a separate unicast address, such as `0x7FFE`, and keep its own sequence counter.
- **Store the sequence counter.** It must only go up, across restarts.
- **The panel sends no status.** Home Assistant has no way to read the light's state. It can track the remote's presses through the proxy, because it can decrypt them.

## Tracking external controls

The integration accepts recognized, authenticated access commands addressed to
`0xFFFF` from external unicast senders (`0x0001` through `0x7FFF`). It excludes
its own `0x7FFE` sender even when those packets return through a panel relay.
Power toggles change a known baseline; scene buttons update the stored effect;
dim taps and holds update the last command. Unknown power remains unknown until
explicitly synchronized. No receive event sends an additional command.

Duplicate identities use sender and Mesh sequence; rapid repeats with new Mesh
sequences use sender and complete access payload, including transaction byte.
Interleaved remotes and buttons do not reset each other's filtering. Repeated
dim holds at the captured 0.6-second cadence remain accepted.

Factory keys authenticate the protocol, but do not prove that a remote is paired
to this particular panel. Other compatible remotes within radio range may also
affect assumed state. Additional sender addresses are covered by software tests;
only the original remote has been physically tested.

## Open questions

- Does the panel accept an unpaired sender other than `0x7FFF`? Turn-on attempts from `0x7FFE` did not illuminate the panel, even after correcting the advertising bearer. The owner reports that the original remote also required pairing before it worked.
- The captured `CF` pairing command authorized `0x7FFE` on this panel: the owner observed blinking during the request, then confirmed HA off/on commands physically worked. The original remote continued working. Other panels' pairing behavior remains unverified. Do not replace the factory network or impersonate `0x7FFF`.
- How can a user unpair `0x7FFE`? Only the pairing request was captured. No unpair or "remove remote" command is known, and no factory reset procedure for the panel is documented. Removing the add-on leaves the pairing in the panel. Finding one needs a capture of the vendor remote or app removing a remote, or a reset procedure from the vendor.
- How long does the panel accept pairing after its mains power returns? The tested panel accepted a request sent straight away. The window was not measured.
- Do separate on and off codes exist? Candidates to try: `03 00 41` and `03 02 41`.
- Relative dim down/up with `0x14` physically worked after transmitter pairing. The exact increment and behavior of other step values remain unmeasured.

## Capture setup

The proxy `bluetooth-proxy-1` (ESP32-C3, `esphome-web-ece638`) did the capture. At ESPHome's default scan settings it listens 30 ms of every 320 ms, and it missed most single presses. On 2026-10-12 its config got `esp32_ble_tracker` scan interval and window of 1100 ms each. After that it caught every press. It dropped off Wi-Fi once, for about 18 seconds, right after the change. It stayed up for the rest of the session. The backup of the old config is `/config/esphome/esphome-web-ece638.yaml.bak-20261012` on the server.

Home Assistant's `bluetooth/subscribe_advertisements` feed does not help. It sends a device only when the device first appears or disappears, not on each advert. The capture polled the Bluetooth diagnostics instead, about twice a second.

## Files

- `tools/meshdec.py` decrypts a capture log. Run `uv run --with cryptography python meshdec.py 11111111111111111111111111111111 capture-2026-10-12.log`.
- `tools/capture-2026-10-12.log` holds the raw mesh adverts from the session, with the panel's constant beacon removed.

## Implementation and packaging

The Home Assistant add-on installs and manages the bundled native integration.
The integration owns command encoding, authenticated reception and the durable
Mesh sequence counter. The add-on uses Home Assistant's native API and does not
create another transmitter or counter. Its Supervisor ingress panel handles
setup, firmware downloads and explicit pairing. The dashboard uses standard
Home Assistant cards and native light, button, select and switch entities.

The light supports the six captured effects and relative dim commands. Separate
on/off BLE commands remain unverified: HA's normal on/off actions decide whether
to send the captured toggle using synchronized power. Same-state requests do
nothing; uncertain toggle requests are never automatically retried. The panel
provides no status feedback, and an exact dim increment remains unmeasured.

Existing integration users retain their entity IDs, config entry, pairing and
sequence Store. Power/effect assumptions are invalidated on restart or proxy
outage. State-correction entities change only those assumptions; the view switch
changes only the dashboard mode. Neither path transmits a BLE command.

Retain the sequence Store across removal or reinstallation. Never reset it,
restore an older counter, or run another sender using `0x7FFE`. Matching factory-key
panels within radio range may all respond; only one factory-network integration
is supported. Permissions, code backup/rollback and removal procedures are in
the [add-on documentation](../philips_skylight/DOCS.md).

Power off/on, Rest/Energize scene changes, relative dimming and original remote
coexistence were physically verified after pairing. Keep that evidence separate
from broader software coverage; see the [validation record](VALIDATION.md).

The firmware adapts
[NicoIIT's MIT-licensed BLE advertising component](https://github.com/NicoIIT/esphome-ble_adv_proxy),
retaining its license and attribution. It uses non-connectable Mesh advertisements,
GAP completion callbacks and a 20 ms advertising interval. Its upstream commit
and local transport changes are recorded in the
[component notes](../esphome/components/ble_adv_proxy/README.md).

## Development installation

Supervisor repository installation needs an accessible repository with the
add-on release on its default branch. Before publishing a release, copy the
`philips_skylight` folder from this checkout to Home Assistant's `/addons`
directory, reload the app store, and install **Philips Skylight** from
**Local apps/add-ons**. The add-on currently uses Supervisor source builds.

To publish prebuilt images, push a tag that matches the `config.yaml` version,
for example `v0.2.5`. The `Publish add-on images` workflow then pushes
`ghcr.io/jphelan82/{amd64,aarch64}-philips-skylight` to the GitHub container
registry. The workflow stops if the tag and the version differ. Supervisor
keeps building from source until `config.yaml` gets this line:

```yaml
image: "ghcr.io/jphelan82/{arch}-philips-skylight"
```

Add that line only after the first images exist and the people who install the
add-on can read the package.

The native integration can also be installed independently through manual
installation or HACS; see the [integration-only guide](INTEGRATION.md).

## Source layout and developer checks

The native integration in `custom_components/philips_skylight` and the firmware
in `esphome` are canonical. `tools/dashboard_card.py` generates the standard
dashboard card. Run `python tools/sync_addon.py` to generate the card and bundle
the integration and firmware into the add-on's self-contained build context.
Its `--check` option verifies parity without modifying files.

The integration's `const.EFFECTS` lists the six modes once. The card generator
reads it directly. The add-on keeps its own copy, and the real-platform test
fails if that copy, or any add-on unique ID, differs from the integration.

Use Python 3.14 for the complete Home Assistant suite:

```sh
python -m pip install homeassistant==2026.6.0 pytest pytest-asyncio pytest-aiohttp ruff
python tools/sync_addon.py --check
python -m pytest -q
ruff check .
```

The Home Assistant dependency supplies PyYAML for card generation; it is also
declared in the project's development test extras. The add-on runtime does not
need PyYAML. Add-on-only tests can run on Python 3.12 with `pytest addon_tests`
when their HTTP/test dependencies are installed.

CI checks generated card and bundle consistency, tests the software on Linux,
and builds amd64/aarch64 containers. It also runs Home Assistant's `hassfest`
check, the HACS (Home Assistant Community Store) validator, and the add-on
linter. If the firmware changes, CI compiles it for an ESP32-C3 with ESPHome
2026.4.5, using the placeholder node in `.github/esphome/ci-node.yaml`. Tests
cover real remote capture authentication,
sequence reservations, native HA entities and reconfiguration, state-only
correction, safe dashboard action targets, installer rollback, ingress/session
access and native API reconnects. The macOS Python 3.14 interpreter-finalization
caveat and physical acceptance results are in the [validation notes](VALIDATION.md).
