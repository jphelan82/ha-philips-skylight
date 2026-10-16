# Philips Skylight for Home Assistant

Control the Philips LED Skylight Ceiling Panel (NatureConnect / BioUp) locally
through an ESPHome Bluetooth advertising proxy. This custom integration creates
one light entity inside Home Assistant; no separate Supervisor app or MQTT broker
is needed. The captured mesh protocol is in [docs/PROTOCOL.md](PROTOCOL.md).

Physically verified on the owner's panel: the power toggle, the Rest, Energize
and Relax modes, a mode turning an off panel on, relative dimming, Set auto rhythm
start, pairing, unpair all, and two paired senders working together: the wall
remote and Home Assistant. See the
[validation notes](VALIDATION.md) for checks and remaining limits.

## Controls and limits

- Assumed-state power and six effects: Refresh, Energize, Focus, Relax, Rest,
  and Auto rhythm.
- Buttons for relative dim up/down and direct scene selection, with the
  remote's icons. A `philips_skylight.dim` action can also hold, like the remote.
- A **Set auto rhythm start** button. It sets the current time as the start of
  the panel's daily schedule. It is not a mode and does not change the recorded
  effect.
- Authenticated remote press tracking across compatible factory-mesh senders,
  with duplicate filtering per sender for panel relays and rapid repeats.
- Separate sender address `0x7FFE`, with durable sequence reservations.

The only confirmed power message is **toggle**. The panel reports no state.
A scene command also turns an off panel on, in that scene. The owner confirmed
this for Relax on 2026-10-13. After any scene command, sent from HA or received
from a remote, the integration records power as on.

Power starts unknown. Before you use `light.turn_off`, or `light.turn_on`
without an effect, synchronize power. A request for the power that Home Assistant
already shows sends nothing.
`light.turn_on` with an effect sends only that scene command, whatever the
recorded power. `light.toggle` can send while power is unknown, but a toggle
cannot establish actual power.

You cannot set a brightness level. The panel takes only "dim down" and "dim
up" commands and never reports its level, so the light has no brightness or
color temperature control. Home Assistant ignores a brightness in
`light.turn_on`. Normal controls send captured commands only, without provisioning
or speculative power codes. Pairing is described below. Commands go to every panel in range, but a panel obeys only the
senders it has paired with. Only one integration entry is allowed, and support
for several panels is not built yet.

## Install

Requires Home Assistant 2026.6 or newer. Firmware was compiled with ESPHome
2026.4.5 for the ESP32-C3 `skylight-proxy`.

1. Back up the proxy YAML. Add
   [esphome/skylight-transmitter.yaml](../esphome/skylight-transmitter.yaml) as a local
   package (`packages: {skylight: !include skylight-transmitter.yaml}`),
   preserving node name, Wi-Fi secrets, API security, OTA, and board settings.
   Copy `esphome/components/ble_adv_proxy` to
   `/config/esphome/components/ble_adv_proxy` on the server first. It contains
   the mesh-compatible advertisement format and GAP completion handling.
   Build and install through ESPHome Device Builder.
2. Confirm the proxy reconnects and exposes
   `esphome.skylight_proxy_adv_svc_v1` (prefix depends on node name), plus
   a **BLE Adv Proxy Name** sensor.
3. Install the integration, then restart Home Assistant. Choose one way:
   - **HACS:** open HACS, then **⋮ → Custom repositories**. Add
     `https://github.com/jphelan82/ha-philips-skylight` with the type
     **Integration**. Then download **Philips Skylight**. HACS shows the
     release tag, which is the add-on's version number.
   - **By hand:** copy `custom_components/philips_skylight` into
     `/config/custom_components/`.
4. Settings → Devices & services → Add integration → Philips Skylight.
   Choose the advertising action and name sensor from the same proxy.
5. Enable **Allow the device to perform Home Assistant actions** in that proxy's
   ESPHome integration options. This lets its firmware publish raw receive
   events for remote tracking. Sending from HA does not require this permission.

## Dashboard card

The integration includes its own dashboard card, **Philips Skylight**. It works
the same as with the add-on, and it needs no extra download from HACS. To add
it, edit a dashboard, select **Add card**, and search for **Philips Skylight**.
Its YAML is one line: `type: custom:philips-skylight-card`.

Home Assistant loads the card when a browser opens Home Assistant. If the card
is not in the card picker after the first install, reload the page in your
browser. The card finds the entities by their unique IDs, so renamed entities
keep working. If an entity that the card uses is disabled, the card names it.
The [dashboard guide](DASHBOARD.md) explains the layout.

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

This records power without sending anything. Standard on/off actions then use
that recorded state. Scene buttons and `light.turn_on` with an effect send the
scene command and record power as on. Synchronize again after a Home Assistant
restart, a panel power cycle or a missed remote press. A proxy reconnect within
60 seconds keeps the record. A longer outage clears it. A successful action means
that the proxy accepted the request. The panel sends no acknowledgment.

## Dimming

Each dim button sends one relative step. For a longer dim, use
`philips_skylight.dim` with a hold time. It sends the remote's hold command
about every 0.6 seconds, as the remote does while you hold its button.

```yaml
action: philips_skylight.dim
target:
  entity_id: light.philips_skylight
data:
  direction: down
  hold: 3
```

## Transmitter pairing

The panel ignores every sender that is not paired, Home Assistant's `0x7FFE`
included. It accepts at most two paired senders, and Home Assistant is one. It
accepts a pairing request only for a short time after it comes back on.

1. Switch the panel's power off at its light switch or breaker, then on again.
2. Wait until the panel is back on. That can take up to 30 seconds.
3. Run `philips_skylight.pair_transmitter` with `confirm: true` straight away.

```yaml
action: philips_skylight.pair_transmitter
target:
  entity_id: light.philips_skylight
data:
  confirm: true
```

The action sends the request twice a second for 10 seconds, 20 requests, like the
remote's own hold, and the panel blinks. A long stream of requests makes the
panel drop the other remote, so the burst stays short. The action returns at
once, and the burst runs in the background. Other commands still get through
between the requests. The light's `pairing_until` attribute shows when the burst
ends. Each request uses a newly reserved sequence number. Pairing never runs by
itself.

Pairing Home Assistant can make the panel drop the other remote. Pair that
remote again afterward, with its own steps, and both work. Pair Home Assistant
only once. To start over, run `philips_skylight.unpair_all_remotes`, pair Home
Assistant, and then pair the remote.

### Pairing and unpairing from Configure

**Configure** on the integration offers **Pair this transmitter** and **Unpair
all remotes**. Each step explains the power cycle and needs a tick box. The
`philips_skylight.pair_transmitter` and `philips_skylight.unpair_all_remotes`
actions do the same for scripts, with `confirm: true`. Both send a 10-second
burst and return at once.

Unpair all remotes sends the pairing request with sub-command `02` instead of
`01`, with the same cadence. Right after power-on, the panel blinks and forgets
every paired sender: the remote and Home Assistant. Outside the pairing window,
it switches the panel off and changes no pairing. No known command removes only
one sender.

## Sequence safety

The HA Store `philips_skylight.sequence_7ffe` reserves 256 sequence values at a
time and saves the high watermark **before** sending. Restarts skip unused
reserved values. Corrupt storage and 24-bit exhaustion fail closed. The
integration saves each block of numbers before it uses them. It does not handle
a disk that cannot be written. Home Assistant's Store logs a failed write and
does not raise an error, so sending continues after a failed save.
Failed sends consume a sequence. Toggles are never automatically retried.

Keep that Store across integration removal/re-addition. Do not reset it, restore
an older copy after sending newer packets, or run another transmitter as
`0x7FFE`: sequence reuse can reuse cryptographic nonces and cause command
rejection. The real remote uses `0x7FFF` and keeps its own counter. IV update and
counter exhaustion recovery are outside this prototype's scope.

### Recover a lost or older Store

The panel drops a packet if its sequence number is not higher than the last
number that the panel accepted from `0x7FFE`. A rebuild without a backup, or a
restore from an older backup, gives the integration a counter that is too low.
The panel then ignores every command from this transmitter, with no error.

If the paired transmitter worked before and now has no effect, call the
`philips_skylight.skip_sequence` action with `confirm: true`. The add-on has the
same control under **Settings and fixes**. The action moves the counter forward
by 1,048,576 and saves it before the next command. It sends no light command and
does not need pairing again. Each skip uses one sixteenth of the 16,777,216
available numbers. The action refuses a skip that leaves no numbers to send.

```yaml
action: philips_skylight.skip_sequence
target:
  entity_id: light.philips_skylight
data:
  confirm: true
```

## Development

Use Python 3.14 and your HA version:

```sh
python -m venv .venv
.venv/bin/pip install homeassistant==2026.6.0 pytest pytest-asyncio ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
node --test tests/test_card.mjs
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
