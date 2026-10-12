import json
from pathlib import Path

import yaml
from skylight_addon import VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_repository_metadata_versions_and_no_broker_dependency():
    config = yaml.safe_load((ROOT / "philips_skylight/config.yaml").read_text())
    manifest = json.loads((ROOT / "philips_skylight/companion/manifest.json").read_text())
    assert config["version"] == manifest["version"] == VERSION
    assert yaml.safe_load((ROOT / "repository.yaml").read_text())["name"]
    assert config["homeassistant_api"] and config["ingress"]
    assert not config.get("services")
    assert not config.get("host_network")
    assert not config.get("privileged")
    assert config["arch"] == ["amd64", "aarch64"]
