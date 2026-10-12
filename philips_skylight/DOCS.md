# Philips Skylight

## Requirements

- Home Assistant OS or Supervised, Core 2026.6 or newer.
- An ESPHome Bluetooth proxy with the bundled `ble_adv_proxy` component.
- A Philips Skylight panel. This protocol was physically tested on the
  NatureConnect/BioUp 17.7 × 25.6 inch model with an ESP32-C3 proxy.

No MQTT broker, cloud account, Wi-Fi credentials in the add-on, direct Bluetooth
hardware access, or long-lived HA token is needed. Supervisor supplies the
native API credential.

## Installation

1. Add this repository to the Home Assistant app/add-on store and install
   **Philips Skylight**. Start it, enable start on boot, and open the web UI.
2. The add-on installs its companion integration into
   `custom_components/philips_skylight`. If requested, use **Restart Home
   Assistant** in the panel to activate it. The add-on never restarts Core
   automatically. Existing integration settings and sequence storage remain intact.
3. For a new transmitter, download the proxy firmware configuration from the
   panel. Copy its `components/ble_adv_proxy` folder next to your ESPHome YAML.
   Merge `skylight-transmitter.yaml` into your existing configuration, retaining
   the node name, Wi-Fi secrets, API encryption, OTA and board settings. Compile
   and install through ESPHome Device Builder. Firmware was tested with
   ESPHome 2026.4.5; the component requires at least that version.
4. In the proxy's ESPHome integration options, enable **Allow the device to
   perform Home Assistant actions**. This allows captured remote presses to
   reach the native light integration.
5. In **Transmitter setup**, choose the advertising action ending in
   `_adv_svc_v1` and the BLE Adv Proxy Name sensor belonging to that same proxy.
   Save. An existing setup can be changed here without recreating its entities.
6. Check the actual panel and use **It is on** or **It is off** to synchronize
   power. HA's standard light controls, effects and dim buttons are now available.

For this owner's existing installation, setup and pairing are already complete.
Installing the add-on preserves `light.philips_skylight` and the eight buttons.
The add-on is a manager/UI for that native integration; it does not introduce a
second BLE transmitter or a second sequence counter.

## Pairing

If the panel ignores commands despite a working advertising proxy, open
**Pair this transmitter**. Switch the panel's mains power off and back on, then
confirm and send the request promptly. It lasts approximately ten seconds; the
panel should blink. Check power, scenes and the original remote afterward.

The original remote continued working on the tested panel, but another unit's
pairing behavior may differ. Have the remote's pairing instructions available.
Pairing never occurs on startup, reconnect or normal control actions. It uses
the captured vendor request, without factory reset or mesh provisioning.

## State and controls

Power and the selected scene are tracked from sent commands and authenticated
remote presses. A remote power press toggles the synchronized power state;
each scene button updates the selected effect. Dim taps and holds update the
last command, without inventing an absolute brightness value. Receive events
update Home Assistant directly and do not send another command to the panel.

Compatible remote senders on the factory mesh are accepted regardless of their
unicast address. Relay copies and rapid transaction repeats are deduplicated
per sender, and the HA transmitter's own packets are ignored. Factory keys are
shared: reception cannot prove a sender is paired to this particular panel.
Another compatible remote in radio range can therefore affect assumed state.

The panel does not report physical status. Synchronize after a Core/proxy
restart, panel mains cycle, outage or missed remote press. Standard on/off
requests require a known baseline; repeating the same request does nothing.
Toggle is explicit and never retried automatically.

Scenes: Refresh, Energize, Focus, Relax, Rest and Auto rhythm. Dimming is relative;
the exact increment has not been measured, so no absolute slider or color
temperature control is exposed. All matching factory-key panels in radio range
may respond. Only one factory-network integration is supported.

## Options and permissions

- **Install the companion integration:** install/update bundled code at startup.
  Disable for manually managed/HACS installations. Newer installed versions
  will not be overwritten.
- **Log level:** debug, info, warning or error.

The add-on needs the native Core API to operate/configure its integration and a
writable Home Assistant configuration mount to install that integration's code.
It writes only the `custom_components/philips_skylight` directory. It never edits
`configuration.yaml`, `.storage`, Wi-Fi secrets or HA credentials. Code backups
and the installation marker live in the add-on's persistent `/data` volume and
are included in Supervisor backups. The native mesh sequence Store remains in
Core's configuration volume and must be retained in Core backups too.

The ingress panel accepts only the Supervisor ingress gateway. No direct port
is exposed. Pairing and Core restarts require explicit confirmation in the UI.
The watchdog tests the web process, allowing Core to restart without causing
the add-on to restart continuously.

## Recovery and removal

Stop the add-on to stop its UI. The native light integration continues operating.
For a complete removal, disable/remove the Philips Skylight integration in
Devices & services, then uninstall the add-on. Keep the sequence Store if this
sender will ever be reused. Do not restore an older mesh counter or run another
transmitter as `0x7FFE`.

If an update fails, the add-on keeps a copy of the previous integration code
under `/data/backups`. Restore only that code, then restart Core; preserve its
current sequence Store. An interrupted directory swap can leave
`custom_components/.philips_skylight-previous`; recover that directory rather
than deleting sequence storage. The add-on refuses another update until that
interrupted installation is resolved.

Firmware rollback requires restoring your backed-up ESPHome YAML, rebuilding
and uploading it. Restoring YAML alone does not change running firmware.
