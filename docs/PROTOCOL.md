# Philips Skylight: Bluetooth Mesh protocol

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
- Do separate on and off codes exist? Candidates to try: `03 00 41` and `03 02 41`.
- Relative dim down/up with `0x14` physically worked after transmitter pairing. The exact increment and behavior of other step values remain unmeasured.

## Capture setup

The proxy `bluetooth-proxy-1` (ESP32-C3, `esphome-web-ece638`) did the capture. At ESPHome's default scan settings it listens 30 ms of every 320 ms, and it missed most single presses. On 2026-10-12 its config got `esp32_ble_tracker` scan interval and window of 1100 ms each. After that it caught every press. It dropped off Wi-Fi once, for about 18 seconds, right after the change. It stayed up for the rest of the session. The backup of the old config is `/config/esphome/esphome-web-ece638.yaml.bak-20261012` on the server.

Home Assistant's `bluetooth/subscribe_advertisements` feed does not help. It sends a device only when the device first appears or disappears, not on each advert. The capture polled the Bluetooth diagnostics instead, about twice a second.

## Files

- `tools/meshdec.py` decrypts a capture log. Run `uv run --with cryptography python meshdec.py 11111111111111111111111111111111 capture-2026-10-12.log`.
- `tools/capture-2026-10-12.log` holds the raw mesh adverts from the session, with the panel's constant beacon removed.
