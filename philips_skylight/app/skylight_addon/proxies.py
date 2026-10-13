"""Match advertised firmware node names to their exact ESPHome action."""

import re


def discover_proxies(states, services, registry):
    sensors = {
        item["entity_id"]: item
        for item in registry
        if item.get("platform") == "esphome" and not item.get("disabled_by")
    }
    candidates = []
    for entity_id, state in sorted(states.items()):
        if (
            not entity_id.startswith("sensor.")
            or entity_id not in sensors
            or not (
                "ble_adv_proxy_name" in entity_id
                or "ble_adv_proxy_name" in sensors[entity_id].get("unique_id", "")
                or sensors[entity_id].get("original_name")
                in ("BLE Adv Proxy Name", "ble_adv_proxy_name")
            )
        ):
            continue
        node = state.get("state", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", node) or node in ("unknown", "unavailable"):
            continue
        service = node.replace("-", "_") + "_adv_svc_v1"
        if service not in services:
            continue
        label = state.get("attributes", {}).get("friendly_name", node)
        label = re.sub(r"[ _]*ble[ _]adv[ _]proxy[ _]name$", "", label, flags=re.I) or node
        candidates.append(
            {
                "entity_id": entity_id,
                "name": label,
                "node": node,
                "transmit_service": service,
            }
        )
    # Duplicate names cannot identify one transmitter safely. Leave those to
    # the explicit advanced selectors instead of guessing from display names.
    return [
        item
        for item in candidates
        if sum(other["transmit_service"] == item["transmit_service"] for other in candidates) == 1
    ]
