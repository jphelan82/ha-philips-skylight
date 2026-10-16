# Validation and physical acceptance

## Software checks

- Decrypted every Mesh Message advertisement in the 2026-10-12 remote capture,
  authenticating network and application MICs.
- Verified factory NetKey network ID `c7cd5342d1544cd5` and AppKey AID `0x38`.
- Exercised reservations with real HA Store files, invalid data, failed writes,
  concurrent power requests, and sequence exhaustion.
- Tested config flow and real light platform setup, actions, proxy outage, and
  unload against Home Assistant 2026.6.0.
- Compiled the pinned transmitter on ESP32-C3 with ESPHome 2026.4.5, then uploaded
  production firmware using the proxy's existing Wi-Fi settings. Dummy Wi-Fi
  build-check firmware was never uploaded.

## Physical acceptance

1. Confirm proxy reconnect and advertising action discovery.
2. Press Focus in HA while watching the physical panel. This avoids guessing a
   power baseline. A successful API request or received advert alone does not
   prove the panel accepts vendor commands from sender `0x7FFE`.
3. Verify the scene visually, synchronize current power, then test off/on and
   repeated requests. Repeated same-state requests should not toggle again.
4. Test scene/dim buttons. Record the physical dim increment before introducing
   an absolute brightness estimate or slider.
5. Press the real remote once; verify HA tracks it once even if a relay copy
   arrives. Confirm the original remote still controls the panel.
6. Restart proxy and HA; verify reconnect, unknown power until resynchronized,
   and an outbound mesh sequence above the previous reservation.

Panel acceptance of a separate sender and the precise dim increment were open
questions in the original notes. Keep physical observations separate from tests.

Initial testing with the unmodified third-party advertiser queued requests but
did not illuminate the physical panel. Its connectable advertising format and
immediate start after raw-data configuration were replaced in the local transport.
The corrected firmware compiled and uploaded successfully, and the proxy's live
log confirmed three non-connectable advertising bursts at a 20ms interval for the
next turn-on attempt. The owner confirmed the physical panel remained off, and
that manually turning it on/off with the paired remote still worked.

An independent Apollo MSR-2 Bluetooth proxy subsequently received the transmitter's
Focus advertisement under BLE address `AA:AA:AA:00:00:03`. The packet authenticated
with the factory keys and decoded as sender `0x7FFE`, sequence `3`, destination
`0xFFFF`, TTL `5`, access payload `c911028304ff0341`. This establishes over-the-air
transmission; it did not establish panel acceptance at that stage. These initial
tests preceded transmitter pairing.

In a fresh comparison, the owner confirmed that the remote turned the panel on
and selected Focus. Its received packet decoded as sender `0x7FFF`, sequence
`160`, TTL `5`, access payload `c911029704ff0341`. Apart from the transaction
byte, this is the same Focus access command transmitted by the integration.

The owner could not confidently distinguish the subsequent HA Relax scene, but
confirmed a further HA toggle did not turn the illuminated panel off. An explicit
experimental pairing action was then prepared and tested against all 13 captured
pairing packets. The updated integration was installed,
Home Assistant restarted, and `philips_skylight.pair_transmitter` was confirmed
available through HA action discovery. The owner then approved pairing, cycled
mains power, and reported the panel blinking during the ten-second request.
The HA action completed without error. A subsequent HA toggle physically turned
the panel off, as confirmed by the owner. This establishes command acceptance
after pairing from `0x7FFE`. The normal HA turn-on action subsequently illuminated
the panel, and the owner confirmed the original remote still controls it.
Its latest captured toggle decoded as sender `0x7FFF`, sequence `164`, access
payload `c811029b030141`, and HA recorded the corresponding remote toggle.
The owner subsequently watched HA select Rest, pause, and return to Energize,
and confirmed both scene changes were visible. Three dim-down steps followed
by three dim-up steps visibly dimmed and brightened the panel. The exact dim
increment remains unmeasured, so no absolute brightness slider is exposed.

The proxy also captured the panel relaying our Energize packet: sender
`0x7FFE`, sequence `289`, TTL `4`, payload `c91102a104ff0241`. The original
transmission used TTL `5`. This corroborates reception by the panel after pairing.

Physical acceptance completed for power off/on, Rest/Energize scene changes,
relative dim down/up, and original remote coexistence. The other four HA scene
buttons match authenticated remote captures but were not individually checked
visually. Pairing persistence through a subsequent panel mains cycle and a
post-pairing HA/proxy restart have not been physically tested. Sequence durability
and reconnect behavior are covered by the software tests below.

On macOS, the 36 tests excluding the real HA platform test exit normally. The
updated real platform test also passes, including registration, confirmation,
and invocation of the pairing action against a fake transport. It was run with
an explicit process exit after pytest and fixture cleanup to avoid the previously
observed Python 3.14.5/3.14.8 interpreter-finalization segfault. That runner issue
remains unresolved locally. The full 47-test suite subsequently passed normally
in GitHub Actions on Linux with Python 3.14 and Home Assistant 2026.6.0.

## Add-on 0.2.0

- Ten add-on tests pass on Python 3.12: installer idempotency and sequence-file
  preservation, code backup/failed-swap recovery, symbolic-link rejection,
  newer-integration preservation, ingress peer checks, CSRF action sessions,
  action allowlist, pairing confirmation, no control replay after a dropped
  native API response, reconnect/event tracking, and repository/version metadata.
- The 36 remaining native-integration tests pass with normal process exit.
  The updated real HA platform test separately passes with the macOS runner
  workaround above, including transmitter reconfiguration, unchanged entity ID
  and sequence reservation advancement.
- Supervisor accepted the local app metadata, built the amd64 container from
  `ghcr.io/home-assistant/base:3.23`, and started it successfully. The s6 startup
  command uses `with-contenv` so Supervisor's credential reaches the application.
- The app authenticated to Core 2026.6.0 through the Supervisor WebSocket and
  REST proxies. Its protected ingress status endpoint returned HTTP 200.
- The installer retained `light.philips_skylight` and the existing sequence
  high watermark `512`. Core restarted to load companion version `0.2.0`; the
  app reconnected automatically and reported no pending restart.
- A protected ingress POST selected Energize through the native button entity
  and returned HTTP 200. The existing Store reserved the next range, advancing
  its high watermark to `768`, without re-pairing or introducing a new counter.
- Start on boot and the Supervisor watchdog are enabled. The UI was visually
  inspected through a local preview using a fake transport; the live app API
  was tested separately. No MQTT dependency was configured.

Both amd64 and aarch64 container builds passed in GitHub Actions after the
release branch was published. Only amd64 has been installed on physical hardware.

## Remote tracking 0.2.1

Regression tests cover a second Mesh sender's power, all six scenes and dim
commands, independent sender transactions, interleaved button retransmissions,
relay duplicate suppression and rejection of our own or invalid senders. The
real Home Assistant platform test checks authenticated receive events update
the native light entity without emitting further control calls. Unknown power
and the captured repeat cadence for dim holds retain their existing behavior.
Additional physical remotes have not been tested.

## Native dashboard controls 0.2.2

The real Home Assistant platform test registers the recorded-scene select and
power correction buttons. It verifies both on and off observations, scene
correction and clearing, remote-driven select updates, invalid-option rejection,
and outage availability. Corrections do not add any transmit calls. The card
export test resolves renamed entities, parses the standard card configuration,
checks correction targets and rejects disabled entities. The local suites now
contain 63 passing tests; the macOS platform runner retains its exit workaround.

## Add-on 0.2.5

Tested on 2026-10-13 with commit `ae8497c`, on the same server, panel and proxy.

### Software checks

- The sync check, 80 pytest tests and ruff pass on macOS with Python 3.14 and
  Home Assistant 2026.6.0. GitHub Actions ran the same checks, the frontend
  test, hassfest, the add-on linter, the container build and the firmware
  compile. All pass. The HACS license check fails until `main` has a LICENSE file.
- Supervisor refused to clone the repository while the disk had 1.0 GB free.
  The owner deleted old backups. With 3.5 GB free, the clone and build worked.
- The local 0.2.4 add-on was stopped and set to manual boot first. Supervisor
  then installed 0.2.5 from the branch repository as `2cef933b_philips_skylight`.
- On first start, the add-on installed integration 0.2.4 and asked for a Core
  restart. After the restart, `light.philips_skylight` kept its entity ID and
  reported `integration_version` 0.2.4.
- The sequence high watermark was `1024` before the update and after the
  restart. The physical tests below moved it to `1280`. It never decreased.
- `philips_skylight.skip_sequence` is registered. A call with `confirm: false`
  was rejected with the intended message, and the Store did not change. The
  REST API returned HTTP 500 for the rejection, because the handler raises
  `HomeAssistantError`. Nobody ran the action with `confirm: true`.
- Through ingress, the status endpoint returned HTTP 200 with the proxy
  `skylight-proxy`, `connected: true` and `restart_required: false`.
  The `/health` endpoint that the Docker health check calls returned `ok`.
- The Supervisor log shows no unhealthy container. Docker's own health status
  was not read, because the SSH add-on has no Docker access.
- The add-on lost its connection during the Core restart. It reconnected about
  2.5 minutes later and logged no errors after that. The 30-second maximum
  backoff caused part of the delay.
- Supervisor turns the watchdog off for a new install. It was turned on again
  to match the old add-on.

### Physical observations

The owner watched the panel. Home Assistant kept power as unknown throughout.

- The owner pressed Relax on the original remote. The light's `assumed_effect`,
  the recorded scene select and the add-on status all changed to Relax.
  The time from press to update was not measured.
- Starting state: the panel was on, probably in Relax. The owner found Relax
  hard to tell apart from the other modes.
- One `light.toggle` from Home Assistant turned the panel off.
- The owner turned the panel on with the original remote. Home Assistant
  recorded that remote toggle.
- One Energize button press changed the panel to Energize.
- One Dim down press visibly dimmed the panel. The step size is still unmeasured.
- Nobody paired the transmitter again. The pairing of sender `0x7FFE` survived
  the add-on change and the Core restart.
- Later the same day, with the panel off, one Relax press from Home Assistant
  turned the panel on in Relax, as the owner confirmed. A mode command
  therefore also turns the panel on. The other five modes were not tested
  from off. They use the same command with a different mode byte.

### Removing the old add-on

After the checks above, the owner approved removing the local 0.2.4 add-on.
Supervisor uninstalled `local_philips_skylight`. The integration stayed at
0.2.4, the watermark stayed at `1280`, and the 0.2.5 add-on kept running.

### Firmware

- The repository's `ble_adv_proxy` component replaced the copy in
  `/config/esphome/components/ble_adv_proxy`. The old copy is in
  `/config/esphome/ble_adv_proxy.bak-20261013`. The node YAML did not change.
- Device Builder validated the node YAML with ESPHome 2026.4.5. It then
  compiled the firmware and installed it over the air to `skylight-proxy`.
- The proxy reconnected to Home Assistant about six minutes after the install
  started. The `skylight_proxy_adv_svc_v1` action came back, and the add-on
  status listed the proxy again with no error.
- A compile through the MCP app proxy does not work. The proxy call times out
  after about two minutes and closes the WebSocket, and Device Builder then
  stops the compile. The install worked from the Device Builder page.
- Physical check: the panel was on in Energize. One `light.toggle` from Home
  Assistant turned it off, as the owner confirmed. The new firmware transmits.

## Add-on 0.2.6

Deployed on 2026-10-13 as an add-on update, followed by a Core restart.

- Supervisor updated the add-on from the branch repository. The add-on
  installed integration 0.2.5. After the Core restart, `light.philips_skylight`
  reported `integration_version` 0.2.5. The watermark stayed at `1280`.
- Core answered HTTP requests 40 seconds after the restart. Supervisor
  reported Core as running at 194 seconds. The add-on retried every five
  seconds and connected one second before that report. Supervisor's WebSocket
  proxy rejects add-ons until Core is running, so the shorter backoff alone
  does not shorten this wait.
- A REST call to `skip_sequence` with `confirm: false` still returned HTTP 500,
  with a logged traceback. The REST API turns only schema errors and unknown
  services into HTTP 400. A `ServiceValidationError` from the handler is not
  enough. Integration 0.2.6 moves the check into the service schema.

## Add-on 0.2.7

Deployed on 2026-10-13 with integration 0.2.6.

### Software checks

- After the Core restart, `integration_version` was 0.2.6 and the watermark
  stayed at `1280`. A REST call to `skip_sequence` with `confirm: false` returned
  HTTP 400.
- `button.philips_skylight_set_auto_rhythm_start` registered with the
  `mdi:clock-start` icon.
- The proxy's connection to Home Assistant dropped about every five minutes
  since at least 12 October, about 90 times in a day. Most drops lasted about
  0.1 seconds, some up to 40 seconds. Each drop resets recorded power and mode
  to unknown, and a command sent during a drop is lost. The proxy's own log
  showed the cause: ESPHome's Wi-Fi roaming switched access points at 11:07:22,
  and Home Assistant's connection stayed dead until 11:08:07. Home Assistant
  recorded only a 0.1-second gap at the end. Add-on 0.2.9 turns roaming off in
  the firmware package and keeps the recorded state through short reconnects.

### Physical observations

- Set auto rhythm start from Home Assistant made the panel blink, as the
  remote's Auto rhythm and Relax combination does. One command was enough.
- Unpair candidate `00`, sent without a power cycle: no visible change. A
  toggle afterward worked.
- Candidate `00`, sent right after power-on: no visible change. The first toggle
  afterward was lost to a proxy drop. A second toggle worked.
- Candidate `02`, sent right after power-on: the panel blinked. Two toggles from
  Home Assistant and the remote's toggles were then all ignored. `02` removes
  every paired sender.
- The owner paired the remote again, and it worked. Home Assistant then sent its
  pairing request after a power cycle, and the panel blinked. A Home Assistant
  toggle and the remote then failed.
- The owner paired the remote again. Then a Home Assistant toggle worked, and
  the remote worked.

*Corrected later the same day.* An earlier version of this section said that a
second "wall remote" was paired and that three senders worked together. The
owner has only one remote, mounted on the wall and usable in the hand. Only two
senders were ever paired: the remote and Home Assistant. See
[Add-on 0.3.1](#add-on-031) for what drops the remote.

## Add-on 0.3.0

Deployed on 2026-10-13 as an add-on update, followed by a Core restart.

### Software checks

- 99 Python tests, 5 page tests, ruff and the bundle check pass locally.
- After the restart, `integration_version` was 0.3.0 and the watermark was
  `1792`. The watermark rose from today's commands and never fell.
- The add-on page opened straight to the status card, because setup was already
  done. It found the proxy's firmware, read the ESPHome remote tracking setting
  through the settings dialog as on, and found Device Builder at
  `/5c53de3b_esphome`.
- The integration's buttons showed the remote's icons, for example
  `mdi:sofa-outline` for Relax and `mdi:brightness-4` for Dim down.
- The old **Skylight** dashboard was deleted. The add-on's **Create a Skylight
  dashboard**, with the full card, built it again at `/skylight-control/panel`
  with the new layout.
- The proxy firmware with `post_connect_roaming: false` ran for 16 minutes with
  no roam and no dropped connection. Before, the connection dropped about every
  five minutes.

### Physical observations

- A 3-second **Dim down** hold from Home Assistant sent the hold command five
  times. The panel dimmed smoothly, by about half. A 3-second **Dim up** hold on
  the remote changed it back by about the same amount. Home Assistant recorded
  the remote's hold as `dim_up`.
- The pairing window ran for Home Assistant, which was already paired. During
  the window, the owner switched the panel's power off and on. The panel
  blinked. **Stop** ended the window, and a toggle from Home Assistant then
  switched the panel off.

## Add-on 0.3.1

Tested on 2026-10-13 with add-on 0.3.0, before the change to 0.3.1.

### Physical observations

- After Home Assistant paired with the 90-second stream, the owner's remote
  stopped working. A clean repeat showed the same: unpair all, pair the remote,
  then pair Home Assistant with the stream. The remote stopped, and Home
  Assistant worked.
- The capture showed the remote still sending, and the panel relaying its
  presses with TTL 4, but the panel did not act on them.
- From another clean unpair all, the owner paired the remote. Then Home
  Assistant paired with one 10-second burst, sent after the owner reported the
  panel back on. The panel blinked. The remote worked, and a Home Assistant
  toggle switched the panel off. Both senders work together.
- After a power cycle, the panel took between a few seconds and about 30 seconds
  to light up again.
- An unpair-all burst that reached the panel after its pairing window had closed
  switched the panel off. Inside the window, the same request made the panel
  blink and forget every sender.

Add-on 0.3.1 removes the 90-second stream. Pairing and unpair all send one
10-second burst, started as soon as the panel is back on.

## Add-on 0.3.3

Deployed on 2026-10-13 with integration 0.3.2.

- The store reload offered 0.3.3, and the update installed it. The add-on
  installed integration 0.3.2 and asked for a Home Assistant restart.
- After the restart, the integration loaded with no new errors. The light shows
  the `mdi:wall-sconce-flat` icon.
- Home Assistant took about four and a half minutes to finish starting. Until
  then, the Supervisor answered the add-on's connection with 502, and the
  add-on retried every 5 seconds. It then connected by itself.
- The recorded power and mode were unknown after the restart.
- Before the deployment, a temporary dashboard showed the new card. The
  owner chose the icon and the order of the icon row from it. The dashboard was
  then deleted.

## Add-on 0.4.0

Deployed on 2026-10-13, with `aiohttp` 3.14.4 and integration 0.3.2. No Home
Assistant restart was needed.

- The add-on tests passed with `aiohttp` 3.14.4 in a separate environment
  before the merge.
- The page follows the open theme. In the dark theme, the page frame carried
  Home Assistant's `#009ac7`, `#111111` and `#1c1c1c`, read from the theme.
- **Needs attention** warned that the test proxy has no API encryption key.
- The test proxy has the Skylight parts written into its YAML, from before the
  package existed. So the page showed no firmware step, as designed. The test
  proxy still runs firmware that forwards every advert.

## Add-on 0.4.18 to 0.4.24

Tested on 2026-10-15 on the owner's panel, with integrations 0.3.3 and 0.3.4.

### Physical observations

- From a clean unpair all, the owner paired the remote, then Home Assistant
  paired with one burst of 30 over 10 seconds. The remote stopped working.
  Pairing the remote again, alone, brought it back, and Home Assistant kept
  working.
- The same order with a burst of 20 at two a second (integration 0.3.3) gave
  the same result. The rate is not the cause.
- After an unpair-all burst from Home Assistant, the owner pressed the add-on's
  power toggle, then the wall remote. The panel ignored both. Unpair all removes
  Home Assistant too. It does not pair Home Assistant again.
- Pairing Home Assistant first and the remote second left both working, each
  time it was tried. Add-on 0.4.23 uses that order.

## Add-on 0.6.0 and 0.6.1

Tested on 2026-10-16 on the owner's Home Assistant, with integration 0.5.0 and
Skylight firmware 3.

- The proxy reported firmware 3 after its install from Device Builder.
- Home Assistant served the card script, and its page loaded it. The browser
  defined `philips-skylight-card` and listed it first in the card picker. The
  console showed no errors.
- **Add card** opens on **By entity**, which lists entities only. On **By
  card**, a search for "Skylight" showed **Philips Skylight** with a live
  preview of the full card. Version 0.6.1 names the tab in the instructions.
- The Skylight dashboard held the one-line card, and it drew the full card.
- A page and the Android app that loaded before the restart showed a
  configuration error for the card. A reload, and a reset of the app's
  frontend cache, fixed it.
- The first restart after the update did not keep the light's state. The light
  ran integration 0.4.0 at shutdown, and that version did not save a state to
  restore. Later restarts save it.
- An integration reload tested the restore. The record was set to on and
  Refresh. The light was unavailable for 17 ms during the reload, then came
  back on, in Refresh. The recorded scene also came back as Refresh. Nothing
  went to the panel.

## Rollback

- Disable the light integration through HA settings. Keep its sequence Store
  intact for future use.
- Restore the proxy's backed-up YAML, compile, and install it to the same device.
  Restoring YAML alone does not change running firmware. Do not restore old HA
  sequence storage.
- Original proxy YAML before raw advertising:
  `/config/esphome/<proxy>.yaml.bak-20261012`.
- YAML just before this deployment:
  `/config/esphome/<proxy>.yaml.bak-skylight-20261012-1718`.
- Component before the 0.2.5 firmware: `/config/esphome/ble_adv_proxy.bak-20261013`.
  Copy it back into `components/ble_adv_proxy`, then compile and install.
