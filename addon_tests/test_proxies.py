from skylight_addon.proxies import discover_proxies


def test_matching_uses_exact_node_and_registered_esphome_sensor_with_renames():
    registry = [
        {
            "entity_id": "sensor.renamed",
            "platform": "esphome",
            "unique_id": "AA-text_sensor-ble_adv_proxy_name",
        },
        {"entity_id": "sensor.b_ble_adv_proxy_name", "platform": "esphome"},
        {"entity_id": "sensor.spoof_ble_adv_proxy_name", "platform": "template"},
    ]
    states = {
        "sensor.renamed": {
            "state": "proxy-a",
            "attributes": {"friendly_name": "Living room proxy"},
        },
        "sensor.b_ble_adv_proxy_name": {"state": "proxy-b"},
        "sensor.spoof_ble_adv_proxy_name": {"state": "proxy-a"},
    }
    services = {"proxy_a_adv_svc_v1": {}, "proxy_b_adv_svc_v1": {}, "other_adv_svc_v1": {}}
    proxies = discover_proxies(states, services, registry)
    assert len(proxies) == 2
    a = next(item for item in proxies if item["node"] == "proxy-a")
    assert a["entity_id"] == "sensor.renamed"
    assert a["transmit_service"] == "proxy_a_adv_svc_v1"
    assert a["name"] == "Living room proxy"
    states["sensor.b_ble_adv_proxy_name"]["state"] = "unavailable"
    assert len(discover_proxies(states, services, registry)) == 1
    registry[0]["disabled_by"] = "user"
    assert discover_proxies(states, services, registry) == []


def test_ambiguous_node_names_and_unmatched_services_are_not_guessed():
    registry = [
        {"entity_id": f"sensor.{name}_ble_adv_proxy_name", "platform": "esphome"}
        for name in ("a", "b")
    ]
    states = {item["entity_id"]: {"state": "proxy"} for item in registry}
    assert discover_proxies(states, {"proxy_adv_svc_v1": {}}, registry) == []
    states[registry[1]["entity_id"]]["state"] = "other"
    assert discover_proxies(states, {"unrelated_adv_svc_v1": {}}, registry) == []
