# Skylight ESPHome package

Use this local package to add Skylight advertising and remote reception to an
existing ESP32 Bluetooth proxy. It includes the tested component source, so no
GitHub account or network fetch is needed for the package itself.

1. Back up the existing ESPHome node YAML.
2. Extract `skylight-transmitter.yaml` and `components/ble_adv_proxy` beside it.
   In ESPHome Device Builder these normally live under `/config/esphome`.
3. Add the Skylight entry to the node's existing `packages` mapping:

   ```yaml
   packages:
     skylight: !include skylight-transmitter.yaml
   ```

   If `packages` already exists, add only the `skylight` entry. Do not create
   a second `packages` key. Keep the node name, board, Wi-Fi secrets, API
   encryption and OTA settings in the node YAML.
4. Check the merged configuration in ESPHome Device Builder, then compile and
   install with ESPHome 2026.4.5 or newer. This package was tested on ESP32-C3.
5. Wait for the proxy to reconnect. Choose it in the Skylight add-on.
6. In its Home Assistant ESPHome integration options, enable **Allow the device
   to perform Home Assistant actions** to receive remote presses.

This uses ESPHome's standard [local package merging](https://esphome.io/components/packages/).
Settings in the node YAML can override package settings. Remove conflicting
`api.custom_services: false` and `api.homeassistant_services: false`, and let
the package provide the BLE scan window/interval if you want continuous
reception. Preserve your API encryption and OTA credentials. Do not duplicate
an existing `ble_adv_proxy` component or add another instance of this package.

The package adds no Wi-Fi network, password, encryption key or OTA credential.
It does not change the node's identity, pair the light or reset its state.
First-time transmitter pairing is a separate, explicit step in the add-on.

The source retains its MIT license and upstream attribution in
`components/ble_adv_proxy/README.md`.
