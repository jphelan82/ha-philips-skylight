# SkyLight State Synchronization

The controller processes `820400` / `820401` from Mesh source `0x3CC2`, addressed to the existing `SOURCE`. GET requests continue to use the existing Mesh codec, sequence allocator, transmission service, and destination. Pairing and firmware remain unchanged.

## Enabling and Testing

Setting `ENABLE_BACKGROUND_QUERIES = False` in `controller.py` disables automatic queries. Manual calls to `philips_skylight.test_onoff_get` still process responses.

1. Back up the currently deployed controller for rollback, then replace it with the updated controller.
2. Restart Home Assistant Core after replacing Python code. Reloading the integration entry alone does not guarantee that modified Python modules are reloaded.
3. Physically turn the lamp on and wait at least five seconds after the last control action.
4. Use `philips_skylight.set_assumed_power` to deliberately set the assumed state to off.
5. Run `philips_skylight.test_onoff_get`. HA should correct the state to on.
6. Repeat with the lamp physically off and the assumed state set to on.
7. After successful tests, set `ENABLE_BACKGROUND_QUERIES = True` and restart Core.
8. Verify polling every 30 seconds, verification five seconds after the last toggle, rapid consecutive toggles, scenes, dimming, and behavior when the proxy goes offline.

The first periodic GET occurs after 30 seconds. All transmissions share the same command lock. The response window lasts three seconds. Even if a response arrives immediately, no second GET is sent within that window. A new control action invalidates a pending query before transmission; the verification task respects the most recent control action. A periodic or manual GET may already satisfy the verification required after a toggle.

If no response arrives, the state remains unchanged. A manual GET during the waiting period is skipped and reported in debug logs. Background tasks stop when the integration is unloaded. The most recently observed STATUS sequence prevents known older responses from being reused during the controller’s lifetime. The existing immediate response to remote commands remains active.

## Limitations and Validation

This GET/STATUS exchange has no request ID. An older response that has never previously been received cannot reliably be identified as stale if it arrives within a new response window. The received sequence tracking does not persist across HA restarts; the existing codec uses a fixed IV index. This is not a complete Mesh replay-protection implementation.

`tests/test_status_sync.py` contains ten test cases for the HA test environment. These ten cases were also run in isolation on Windows using simulated HA interfaces. This validates controller behavior, not the actual HA event bus or hardware. Ruff and Python syntax checks pass. The full pytest suite could not run locally because Home Assistant is not installed. Functional verification with the physical lamp is still required.

Rollback: restore the backed-up controller and restart Core. Do not restore an older version of the Mesh sequence store. For other lamps, `STATUS_SOURCE` must be adjusted.