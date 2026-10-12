# Philips Skylight for Home Assistant

A Home Assistant add-on for local Philips Skylight power, scenes, relative
dimming, pairing and setup through an ESPHome Bluetooth proxy.

**No MQTT broker or cloud account is required.** The add-on installs a bundled
native integration that exposes `light.philips_skylight` and scene/dim buttons.
Its authenticated ingress panel manages setup and controls through the native
Home Assistant API. The integration owns the BLE protocol and durable sequence
counter; the add-on does not create a second transmitter.

Physically verified after transmitter pairing: power off/on, Rest/Energize scene
switching, relative dimming, and continued original remote control.

## Install

Requires Home Assistant OS/Supervised, Core 2026.6+, and an ESPHome advertising
proxy. Firmware is tested on ESP32-C3 with ESPHome 2026.4.5.

1. Add this repository to Settings → Apps/Add-ons → Store → Repositories:
   `https://github.com/jphelan82/ha-philips-skylight`.
2. Install **Philips Skylight**, start it, and open its web UI.
3. If prompted, restart Home Assistant to activate the bundled integration.
4. Select your advertising proxy in **Transmitter setup**. The panel provides
   downloadable firmware configuration for a proxy that needs the advertising
   component. Compile/install it through ESPHome Device Builder.
5. Synchronize the panel's current power. If commands are ignored, follow the
   explicit transmitter-pairing procedure in the panel.

The repository must contain this release before repository installation will
work. Until then, copy the `philips_skylight` folder into HA's `/addons` directory,
reload the store, and install it from **Local apps/add-ons**.

See [add-on documentation](philips_skylight/DOCS.md) for firmware, installation,
permissions, pairing, recovery and removal. Existing users of the prototype keep
their native entity IDs, integration settings, pairing and sequence Store.

## Controls and state

- Native light: power and six effects (Refresh, Energize, Focus, Relax, Rest,
  Auto rhythm).
- Buttons: relative dim up/down and direct scene selection.
- Ingress: controls, power synchronization, transmitter setup/reconfiguration,
  firmware download and explicit pairing.
- Authenticated remote tracking for power, scenes and dim commands, with
  duplicate filtering per sender and exclusion of our own relayed commands.

The panel reports no physical status. Power is assumed from commands and remote
presses. Synchronize it after a Core/proxy restart, panel mains cycle, outage or
missed press. The dim increment is not measured, so no absolute brightness or
color-temperature slider is exposed. Same-state on/off requests do nothing;
uncertain toggle requests are never automatically retried.

The transmitter uses `0x7FFE`, while the original remote uses `0x7FFF`. Keep the
native integration's sequence Store across removal/reinstallation; never reset
or restore an older counter or run a second sender with that address. Matching
factory-key panels in range can all respond. Only one factory-network setup is
supported.

## Development

The native integration in `custom_components/philips_skylight` and firmware in
`esphome` are canonical. `python tools/sync_addon.py` bundles them into the add-on's
self-contained Docker build context; `--check` verifies the bundle without edits.
CI checks source parity, runs software tests and builds amd64/aarch64 containers.
Container publishing is a separate release step; the add-on currently supports
Supervisor source builds.

Use Python 3.14 for the complete HA test suite. The add-on alone can be tested
on Python 3.12 with `pytest addon_tests` and its HTTP/test dependencies installed.

```sh
python -m pip install homeassistant==2026.6.0 pytest pytest-asyncio pytest-aiohttp ruff
python tools/sync_addon.py --check
python -m pytest -q
ruff check .
```

Tests cover captured protocol authentication, sequence reservations, HA entities
and reconfiguration, installer rollback, ingress/session access and native API
reconnects. The macOS Python 3.14 finalization caveat and physical checks are in
[validation notes](docs/VALIDATION.md).

The native integration remains usable independently through manual installation
or HACS; see [integration-only instructions](docs/INTEGRATION.md).

Protocol research: [decoded commands](docs/PROTOCOL.md). The firmware adapts
[NicoIIT's MIT-licensed BLE advertising component](https://github.com/NicoIIT/esphome-ble_adv_proxy),
retaining its license and attribution. Our adaptation uses non-connectable Mesh
advertisements and GAP completion callbacks. See its [component notes](esphome/components/ble_adv_proxy/README.md).
