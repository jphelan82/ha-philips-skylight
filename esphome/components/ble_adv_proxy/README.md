# Mesh transport changes

Vendored from NicoIIT/esphome-ble_adv_proxy at
`d7412240e7edd21b5717b3c6d3235aa1aeaf64cf`, under the adjacent MIT LICENSE.

Local changes: use non-connectable advertisements for the Bluetooth Mesh bearer,
wait for GAP configuration/start/stop completion callbacks, and advertise each
burst at a 20ms interval. The raw API actions and receive event format are unchanged.
The local component targets ESPHome 2026.4.5.

Copy this directory to `/config/esphome/components/ble_adv_proxy` on the HA server
before building a proxy with the local external component configuration.
