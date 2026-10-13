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
3. For a new transmitter, download the ESPHome Skylight package from the
   panel. Extract `skylight-transmitter.yaml` and `components/ble_adv_proxy`
   beside the existing node YAML. Add a local package entry:

   ```yaml
   packages:
     skylight: !include skylight-transmitter.yaml
   ```

   If `packages` already exists, add just the `skylight` entry. Preserve the
   node name, Wi-Fi secrets, API encryption, OTA and board settings. Validate,
   compile and install through ESPHome Device Builder, using ESPHome 2026.4.5
   or newer. The download includes instructions and tested component source.
   Your node's settings can override the package; remove conflicting disabled
   API custom/Home Assistant services and allow the package's BLE scan settings.
4. In **Transmitter settings**, select a **Bluetooth proxy** and save. One
   compatible proxy is automatically selected. Advanced action/sensor selectors
   are available for custom adapter names or unmatched proxies; both must refer
   to the same device. Existing settings are not changed until you save.
5. Enable **Allow the device to perform Home Assistant actions** in the proxy's
   ESPHome integration options. This allows received remote presses to reach
   the integration. Finding a transmitter does not verify this permission.
6. **Pair the HA transmitter on first setup**, following the explicit pairing
   procedure below. Already paired, working installations skip this step.
7. **Record initial state before first use.** Observe the physical panel and
   select its power. For the mode, optionally press a mode button on the existing
   control panel. The dropdown always updates from
   the integration's recorded mode as received presses arrive. A manual choice
   records it immediately; choose **Unknown** if unsure. Save power with **Record initial
   state**. Saving sends no light command and keeps the latest mode
   without overwriting a newer press. A physical mode press operates the light;
   receiving it is not confirmation the light changed. Power needs an observation
   because its toggle cannot establish an unknown on/off state. If the dropdown
   does not respond within a few seconds, check permission and proxy range.
   Repeat after pairing or an outage.
8. **Optional:** choose Compact or Full in **Dashboard controls** and create a
   dedicated dashboard or add a card to an existing editable view. You can use
   only native entities instead; creating a dashboard is not a setup requirement.

Only relevant setup guidance is expanded. After recording the initial state,
firmware/transmitter/permission/pairing details collapse under **Setup and recovery**.
An unknown power state opens **Record initial state** again without repeating
transmitter setup or pairing. The first-setup guide survives add-on restarts until
its starting-state form has been completed.

If you already use the Philips Skylight integration, the add-on preserves your
existing entities, transmitter setup and pairing. Repeat pairing only if the
panel ignores commands. The add-on manages the same integration and does not
introduce a second transmitter or sequence counter.

## Pairing

A new HA transmitter needs pairing before the panel accepts its commands. Open
**Pair the transmitter on first setup**. Skip it if the existing transmitter
already works; normal add-on updates do not require re-pairing. Switch the panel's mains power off and back on, then
confirm and send the request promptly. It lasts approximately ten seconds; the
panel should blink. Check power, scenes and the original remote afterward.

The original remote continued working on the tested panel, but another unit's
pairing behavior may differ. Have the remote's pairing instructions available.
Pairing never occurs on startup, reconnect or normal control actions. It uses
the captured vendor request, without factory reset or mesh provisioning.

## State and controls

For everyday use, optionally add the standard Skylight card to a Home Assistant
dashboard. **Create Skylight dashboard** creates a dedicated dashboard or opens
the existing one without replacing it. **Add card to an existing dashboard**
adds the selected card to a chosen editable view and preserves its other cards.
Compact is the default; Full adds headings and everyday instructions.

The add-on uses the Lovelace API, never storage-file edits. It checks a dashboard
revision before adding a card and avoids an identical duplicate. It cannot take
control of generated dashboards or add to panel views; use the manual download
for those cases and for YAML dashboards. Download either card and paste it into
**Edit dashboard → Add card → Manual**. The actual entity IDs are filled in.
These are reusable built-in card configurations, rather than a new custom card
type in the picker. No custom resource or HACS dependency is required.

The card has one power toggle and highlights the recorded mode in blue; other
modes are gray. **Correct recorded state** at the bottom replaces the normal
controls with **Panel is on/off** and mode choices. These update assumed state
without sending a command. Choose **Mode unknown** if you cannot identify the
scene, then **Done** to return to normal controls. The underlying native entities can
also be added individually from the dashboard editor; no helper or automation
is needed. They appear in the Skylight device's Configuration section.

The physical remote's held dim packets are recognized. Dashboard dim buttons
send one relative step per tap; holding a tile does not continuously dim.

Power and the selected scene are tracked from sent commands and authenticated
BLE button calls from other compatible remote/control panels in range, including
commands relayed by light panels. A remote power press toggles the synchronized
power state;
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

### Reliability and command-only use

Recorded state is an estimate, not status feedback from the light. Missed BLE
events, wall switches or mains interruptions, Home Assistant/proxy downtime,
ignored commands and calls intended for other nearby panels can make it wrong.
Matching the state at setup, and correcting it later, only establishes the
current baseline; it does not prevent future drift.

If tracking is unreliable in your installation, use the card's direct power
toggle, mode buttons and relative dim buttons without relying on entity states
or the selected-mode highlight. Automations can use `light.toggle` or the
appropriate native `button.press` action. Do not use estimated state as a
condition or as confirmation that the physical light responded. Standard
`light.turn_on`/`light.turn_off` choose whether to toggle based on the recorded
power; a wrong baseline can cause a no-op or an unwanted toggle. Direct commands
avoid that decision, but still need physical verification when the final state
matters. A toggle cannot guarantee on or off with an unknown baseline.

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
Its filesystem installer writes only the `custom_components/philips_skylight`
directory. Optional dashboard changes use the native Lovelace API. It never edits
`configuration.yaml`, `.storage`, Wi-Fi secrets or HA credentials. Code backups
and the installation marker live in the add-on's persistent `/data` volume and
are included in Supervisor backups. The native mesh sequence Store remains in
Core's configuration volume and must be retained in Core backups too.

The ingress panel accepts only the Supervisor ingress gateway. No direct port
is exposed. Pairing and Core restarts require explicit confirmation in the UI.
A Docker health check inside the container reads only the `/health` page. It
tests the web process, not Core, so a Core restart does not restart the add-on.

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

If the paired transmitter worked before, but the panel ignores it after Home
Assistant was rebuilt without a backup or restored from an older backup, the
mesh sequence counter is too low. Open **Setup and recovery → Panel ignores
commands after a rebuild or restore**, confirm, and select **Skip sequence
forward**. The counter moves forward by about one million. The skip sends no
light command and does not need pairing again. Each skip uses one sixteenth of
the counter's range, so use it only for this problem.

Firmware rollback requires restoring your backed-up ESPHome YAML, rebuilding
and uploading it. Restoring YAML alone does not change running firmware.
