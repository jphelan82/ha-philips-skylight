import json
from pathlib import Path

import yaml
from skylight_addon import VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_repository_metadata_versions_and_no_broker_dependency():
    config = yaml.safe_load((ROOT / "philips_skylight/config.yaml").read_text())
    manifest = json.loads((ROOT / "philips_skylight/companion/manifest.json").read_text())
    assert config["version"] == VERSION
    assert tuple(map(int, manifest["version"].split("."))) <= tuple(map(int, VERSION.split(".")))
    # The integration's version lives in its manifest, const.py and pyproject.toml.
    canonical = json.loads(
        (ROOT / "custom_components/philips_skylight/manifest.json").read_text()
    )["version"]
    const = (ROOT / "custom_components/philips_skylight/const.py").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert manifest["version"] == canonical
    assert f'VERSION = "{canonical}"' in const
    assert f'\nversion = "{canonical}"\n' in pyproject
    # Supervisor passes BUILD_VERSION; a stale default in the Dockerfile only misleads.
    assert "ARG BUILD_VERSION\n" in (ROOT / "philips_skylight/Dockerfile").read_text()
    assert yaml.safe_load((ROOT / "repository.yaml").read_text())["name"]
    # Home Assistant downloads this image, so it must match what the workflow publishes.
    publish = (ROOT / ".github/workflows/addon-publish.yml").read_text()
    assert config["image"] == "ghcr.io/jphelan82/{arch}-philips-skylight"
    assert "ghcr.io/jphelan82/${{ matrix.arch }}-philips-skylight:" in publish
    assert config["homeassistant_api"] and config["ingress"]
    assert not config.get("services")
    assert not config.get("host_network")
    assert not config.get("privileged")
    assert config["arch"] == ["amd64", "aarch64"]
