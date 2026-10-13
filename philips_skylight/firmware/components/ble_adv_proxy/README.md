# Mesh transport changes

Vendored from NicoIIT/esphome-ble_adv_proxy at
`d7412240e7edd21b5717b3c6d3235aa1aeaf64cf`, under the adjacent MIT LICENSE.

Local changes: use non-connectable advertisements for the Bluetooth Mesh bearer,
wait for GAP configuration/start/stop completion callbacks, and advertise each
burst at a 20ms interval. Duplicate-packet expiry compares times by difference,
so it keeps working after `millis()` rolls over at about 49 days. The runtime
patch of ESPHome's `api` schema and the support code for ESPHome releases older
than 2026.4 are removed. `skylight-transmitter.yaml` sets the two `api` options
that the patch used to force on. The raw API actions and receive event format
are unchanged. The proxy forwards only adverts that carry a Bluetooth mesh
message (AD type 0x2A). Upstream forwards every advert it hears, which puts
every nearby phone and watch into Home Assistant's event log.
The local component targets ESPHome 2026.4.5.

Copy this directory to `/config/esphome/components/ble_adv_proxy` on the HA server
before building a proxy with the local external component configuration.
