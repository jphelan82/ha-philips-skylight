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
        {
            "file": "manual.yaml",
            "node": "manual",
            "friendly_name": "Proxy",
            "has_skylight": True,
            "uses_package": False,
            "api_key": False,
        },
        {
            "file": "proxy.yaml",
            "node": "proxy-1",
            "friendly_name": "Proxy",
            "has_skylight": False,
            "uses_package": False,
            "api_key": False,
        },
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


def test_firmware_version_is_read_from_the_package():
    assert esphome_files.firmware_version((FIRMWARE / "skylight-transmitter.yaml").read_text())
    assert esphome_files.firmware_version("substitutions:\n  skylight_firmware: '7'\n") == "7"
    assert esphome_files.firmware_version("esphome:\n  name: x\n") is None


def test_update_files_refreshes_old_copies_and_keeps_backups(tmp_path):
    node = tmp_path / "proxy.yaml"
    node.write_text(PROXY)
    with pytest.raises(ValueError, match="No Bluetooth proxy"):
        esphome_files.update_files(tmp_path, FIRMWARE)
    esphome_files.install_package(tmp_path, FIRMWARE, "proxy.yaml")
    assert esphome_files.files_current(tmp_path, FIRMWARE)
    assert esphome_files.update_files(tmp_path, FIRMWARE) == {"changed": False, "backups": []}

    # An older package and component, as after an add-on update.
    package = tmp_path / "skylight-transmitter.yaml"
    package.write_text("# old package\n")
    (tmp_path / "components/ble_adv_proxy/ble_adv_proxy.h").write_text("// old")
    node_text = node.read_text()
    assert not esphome_files.files_current(tmp_path, FIRMWARE)
    result = esphome_files.update_files(tmp_path, FIRMWARE)
    assert result["changed"] is True
    assert esphome_files.files_current(tmp_path, FIRMWARE)
    assert node.read_text() == node_text
    package_backup, component_backup = result["backups"]
    assert (tmp_path / package_backup).read_text() == "# old package\n"
    assert (tmp_path / component_backup / "ble_adv_proxy.h").read_text() == "// old"


def test_a_missing_copy_is_not_current(tmp_path):
    assert not esphome_files.files_current(tmp_path, FIRMWARE)


def test_api_key_is_found_only_under_api():
    keyed = PROXY + "api:\n  encryption:\n    key: !secret proxy_key\n"
    assert esphome_files.has_api_key(keyed)
    assert not esphome_files.has_api_key(PROXY + "api:\n  reboot_timeout: 0s\n")
    assert not esphome_files.has_api_key(PROXY + "api:\n\nother:\n  encryption: x\n")
    assert not esphome_files.has_api_key(PROXY)


def test_names_resolve_substitutions():
    text = (
        "substitutions:\n  name: kitchen-proxy\n  friendly_name: Kitchen Proxy\n"
        "esphome:\n  name: ${name}\n  friendly_name: ${friendly_name}\n"
    )
    assert esphome_files.friendly_name(text) == "Kitchen Proxy"
    assert esphome_files._node_name(text, "file") == "kitchen-proxy"
    unknown = "esphome:\n  name: ${x}\n  friendly_name: ${y}\n"
    assert esphome_files.friendly_name(unknown) is None
    assert esphome_files._node_name(unknown, "file") == "file"
