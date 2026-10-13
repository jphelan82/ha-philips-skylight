from pathlib import Path

import pytest
from skylight_addon import esphome_files

FIRMWARE = Path(__file__).resolve().parents[1] / "philips_skylight/firmware"
PROXY = """esphome:
  name: proxy-1
  friendly_name: Proxy

wifi:
  ssid: !secret wifi_ssid

bluetooth_proxy:
  active: true
"""


def test_lists_only_bluetooth_proxies(tmp_path):
    (tmp_path / "proxy.yaml").write_text(PROXY)
    (tmp_path / "sensor.yaml").write_text("esphome:\n  name: sensor\n")
    (tmp_path / "secrets.yaml").write_text("bluetooth_proxy:\n")
    (tmp_path / "manual.yaml").write_text(PROXY.replace("proxy-1", "manual") + "ble_adv_proxy:\n")
    assert esphome_files.list_nodes(tmp_path) == [
        {"file": "manual.yaml", "node": "manual", "has_skylight": True},
        {"file": "proxy.yaml", "node": "proxy-1", "has_skylight": False},
    ]
    assert esphome_files.list_nodes(tmp_path / "missing") == []


def test_package_line_is_added_once_in_the_right_place():
    added = esphome_files.add_package_line(PROXY)
    assert added.endswith("\npackages:\n  skylight: !include skylight-transmitter.yaml\n")
    assert esphome_files.add_package_line(added) == added
    existing = PROXY + "packages:\n    base: !include base.yaml\n"
    assert "packages:\n    skylight: !include skylight-transmitter.yaml\n    base:" in (
        esphome_files.add_package_line(existing)
    )
    with pytest.raises(ValueError, match="by hand"):
        esphome_files.add_package_line(PROXY + "packages: !include_dir_named packages\n")


def test_install_copies_the_package_and_keeps_a_backup(tmp_path):
    node = tmp_path / "proxy.yaml"
    node.write_text(PROXY)
    result = esphome_files.install_package(tmp_path, FIRMWARE, "proxy.yaml")
    assert result["changed"] is True
    assert (tmp_path / result["backup"]).read_text() == PROXY
    assert "skylight: !include skylight-transmitter.yaml" in node.read_text()
    assert (tmp_path / "skylight-transmitter.yaml").read_bytes() == (
        FIRMWARE / "skylight-transmitter.yaml"
    ).read_bytes()
    component = tmp_path / "components/ble_adv_proxy"
    assert (component / "ble_adv_proxy.cpp").is_file()

    # A second run changes nothing and makes no new backup.
    again = esphome_files.install_package(tmp_path, FIRMWARE, "proxy.yaml")
    assert again == {"file": "proxy.yaml", "changed": False, "backup": None}

    # A different component already in place is kept as a backup first.
    (component / "ble_adv_proxy.cpp").write_text("// old")
    esphome_files.install_package(tmp_path, FIRMWARE, "proxy.yaml")
    backups = list(tmp_path.glob("ble_adv_proxy.bak-*"))
    assert len(backups) == 1
    assert (backups[0] / "ble_adv_proxy.cpp").read_text() == "// old"


def test_install_refuses_unknown_files(tmp_path):
    (tmp_path / "proxy.yaml").write_text(PROXY)
    for name in ("other.yaml", "../proxy.yaml", "secrets.yaml"):
        with pytest.raises(ValueError, match="Choose one"):
            esphome_files.install_package(tmp_path, FIRMWARE, name)
