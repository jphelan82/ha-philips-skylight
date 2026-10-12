# Philips Skylight for Home Assistant

Control the Philips LED Skylight Ceiling Panel (NatureConnect / BioUp) locally
through an ESPHome Bluetooth advertising proxy. This custom integration creates
one light entity inside Home Assistant; no separate Supervisor app or MQTT broker
is needed. The captured mesh protocol is in [docs/PROTOCOL.md](PROTOCOL.md).

Physically verified on the owner's panel after transmitter pairing: power on/off,
Rest/Energize scene switching, relative dimming, and continued original remote
control. See [validation notes](VALIDATION.md) for checks and remaining limits.

## Controls and limits

- Assumed-state power and six effects: Refresh, Energize, Focus, Relax, Rest,
  and Auto rhythm.
- Buttons for relative dim up/down and direct scene selection.
- Authenticated remote press tracking across compatible factory-mesh senders,
  with duplicate filtering per sender for panel relays and rapid repeats.
- Separate sender address `0x7FFE`, with durable sequence reservations.

The only confirmed power message is **toggle**. The panel reports no state.
Power starts unknown: synchronize it before using `light.turn_on` or
`light.turn_off`. Same-state requests do nothing. `light.toggle` and scene buttons
can send while power is unknown, but cannot establish actual power.

Absolute brightness and color temperature are not exposed: dim step size is
unverified. Normal controls send captured commands only, without provisioning
or speculative power codes. A separate experimental pairing action is described
below. Factory-key commands broadcast to all
matching panels in radio range; only one integration entry is allowed.

## Install

Requires Home Assistant 2026.6 or newer. Firmware was compiled with ESPHome
2026.4.5 for the ESP32-C3 `bluetooth-proxy-1`.

1. Back up the proxy YAML. Add
   [esphome/skylight-transmitter.yaml](../esphome/skylight-transmitter.yaml) as a local
   package (`packages: {skylight: !include skylight-transmitter.yaml}`),
   preserving node name, Wi-Fi secrets, API security, OTA, and board settings.
   Copy `esphome/components/ble_adv_proxy` to
   `/config/esphome/components/ble_adv_proxy` on the server first. It contains
   the mesh-compatible advertisement format and GAP completion handling.
   Build and install through ESPHome Device Builder.
2. Confirm the proxy reconnects and exposes
   `esphome.esphome_web_ece638_adv_svc_v1` (prefix depends on node name), plus
   a **BLE Adv Proxy Name** sensor.
3. Copy `custom_components/philips_skylight` into HA's
   `/config/custom_components/` and restart HA. Once published, this repository
   can also be added as a custom **Integration** repository in HACS.
4. Settings → Devices & services → Add integration → Philips Skylight.
   Choose the advertising action and name sensor from the same proxy.
5. Enable **Allow the device to perform Home Assistant actions** in that proxy's
   ESPHome integration options. This lets its firmware publish raw receive
   events for remote tracking. Sending from HA does not require this permission.

## Synchronize power

Check whether the physical panel is illuminated, then run
`philips_skylight.set_assumed_power` in Developer Tools → Actions:

```yaml
action: philips_skylight.set_assumed_power
target:
  entity_id: light.philips_skylight
data:
  is_on: true
```

This records power without transmitting. Standard on/off and effect actions
then use that assumed state. Scene buttons select a scene without making a power
assumption. Synchronize again after an HA restart, proxy outage, panel power
cycle, or missed remote press. A proxy outage invalidates assumed power/effect.
A successful HA action means the proxy accepted the transmission request; the
panel does not acknowledge it.

## Transmitter pairing

Initial commands from our separate sender were ignored even though an independent
proxy received authenticated advertisements. After sending the captured pairing
request from `0x7FFE`, the owner confirmed physical HA power control and that the
original remote still works on this panel. The explicit experimental
`philips_skylight.pair_transmitter` action sends that request. Pairing behavior
on other panels is unverified and may replace an existing remote's pairing.
It never runs during setup,
reconnect, or normal light controls. No factory reset or network provisioning
is performed.

On first setup, when ready to pair, cycle the panel's mains power and invoke
the action with `confirm: true`, targeting only `light.philips_skylight`. It
sends 30 requests at approximately three per second, using a freshly reserved
sequence for each. Afterward, check the physical light and both controllers.
Power remains unknown until synchronized; action completion is not a pairing
acknowledgment. Have the original remote's pairing instructions available.

## Sequence safety

The HA Store `philips_skylight.sequence_7ffe` reserves 256 sequence values at a
time and saves the high watermark **before** sending. Restarts skip unused
reserved values. Corrupt storage, failed writes, and 24-bit exhaustion fail
closed. Failed sends consume a sequence; toggles are never automatically retried.

Keep that Store across integration removal/re-addition. Do not reset it, restore
an older copy after sending newer packets, or run another transmitter as
`0x7FFE`: sequence reuse can reuse cryptographic nonces and cause command
rejection. The real remote uses `0x7FFF` and keeps its own counter. IV update and
counter exhaustion recovery are outside this prototype's scope.

## Development

Use Python 3.14 and your HA version:

```sh
python -m venv .venv
.venv/bin/pip install homeassistant==2026.6.0 pytest pytest-asyncio ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Tests cover capture decryption, authentication failures, durable reservations,
concurrency, transport errors, relay duplicates, config flow, and the real HA
entity platform lifecycle. Physical checks and rollback are documented in
[docs/VALIDATION.md](VALIDATION.md).

The transport adapts [NicoIIT's BLE advertising component](https://github.com/NicoIIT/esphome-ble_adv_proxy)
for raw transmit actions and `esphome.ble_adv.raw_adv` events. See the
[ESPHome Native API documentation](https://esphome.io/components/api/) for device
actions in Home Assistant.

The local adaptation uses non-connectable Mesh advertisements and waits for
controller callbacks before timing/stopping each advertising burst.
