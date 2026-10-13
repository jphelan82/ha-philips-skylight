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
Focus advertisement under BLE address `1C:DB:D4:EC:E6:3A`. The packet authenticated
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
  `esphome-web-ece638`, `connected: true` and `restart_required: false`.
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
- A mode command sent while the panel is off was not tested.

## Rollback

- Disable the light integration through HA settings. Keep its sequence Store
  intact for future use.
- Restore the proxy's backed-up YAML, compile, and install it to the same device.
  Restoring YAML alone does not change running firmware. Do not restore old HA
  sequence storage.
- Original proxy YAML before raw advertising:
  `/config/esphome/esphome-web-ece638.yaml.bak-20261012`.
- YAML just before this deployment:
  `/config/esphome/esphome-web-ece638.yaml.bak-skylight-20261012-1718`.
