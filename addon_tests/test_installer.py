import json

import pytest
from skylight_addon.installer import Installer


@pytest.fixture
def installer(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text(
        json.dumps({"domain": "philips_skylight", "version": "0.2.0"})
    )
    (source / "light.py").write_text("NEW = True\n")
    return Installer(source, tmp_path / "ha", tmp_path / "data")


def test_install_is_idempotent_and_never_changes_sequence_storage(installer):
    storage = installer.ha_config / ".storage/philips_skylight.sequence_7ffe"
    storage.parent.mkdir(parents=True)
    storage.write_text('{"data":{"high_watermark":1024}}')
    assert installer.install()
    assert installer.pending_restart
    assert not installer.install()
    assert storage.read_text() == '{"data":{"high_watermark":1024}}'
    installer.mark_restarted()
    assert not Installer(installer.source, installer.ha_config, installer.data).pending_restart


def test_update_backups_only_companion_and_keeps_old_version_on_failed_swap(installer, monkeypatch):
    installer.target.mkdir(parents=True)
    (installer.target / "manifest.json").write_text(
        json.dumps({"domain": "philips_skylight", "version": "0.1.0"})
    )
    (installer.target / "light.py").write_text("OLD = True\n")
    from skylight_addon import installer as module

    replace = module.os.replace

    def fail_staging(source, destination):
        if ".philips_skylight-" in str(source) and source.name != ".philips_skylight-previous":
            raise OSError("disk full")
        replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_staging)
    with pytest.raises(OSError, match="disk full"):
        installer.install()
    assert (installer.target / "light.py").read_text() == "OLD = True\n"
    assert len(list((installer.data / "backups").iterdir())) == 1
    assert not installer.pending_restart


def test_installer_refuses_symlinks_and_newer_integration(installer, tmp_path):
    installer.target.parent.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    installer.target.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"):
        installer.install()
    installer.target.unlink()
    installer.target.mkdir()
    (installer.target / "manifest.json").write_text(
        json.dumps({"domain": "philips_skylight", "version": "9.0.0"})
    )
    assert not installer.install()
    assert json.loads((installer.target / "manifest.json").read_text())["version"] == "9.0.0"


def test_an_interrupted_install_is_recovered_first(installer):
    previous = installer.target.parent / ".philips_skylight-previous"
    previous.mkdir(parents=True)
    (previous / "manifest.json").write_text(
        json.dumps({"domain": "philips_skylight", "version": "0.1.0"})
    )
    (previous / "light.py").write_text("OLD = True\n")
    assert installer.install()
    assert not previous.exists()
    assert (installer.target / "light.py").read_text() == "NEW = True\n"
    # The recovered old version was kept as a backup before the update.
    (backup,) = (installer.data / "backups").iterdir()
    assert (backup / "light.py").read_text() == "OLD = True\n"


def test_damaged_installs_never_raise_anything_but_a_clear_error(installer):
    installer.target.mkdir(parents=True)
    (installer.target / "light.py").write_text("PARTIAL = True\n")
    # A folder without manifest.json is incomplete, so it is replaced.
    assert installer.install()
    assert installer.error is None
    (installer.target / "manifest.json").write_text(
        json.dumps({"domain": "philips_skylight", "version": "0.3.0b1"})
    )
    with pytest.raises(ValueError, match="version"):
        installer.install()
    assert "not installed" in installer.error
    (installer.target / "manifest.json").write_text("{not json")
    with pytest.raises(ValueError, match="damaged"):
        installer.install()


def test_an_unreadable_marker_does_not_stop_startup(installer):
    installer.data.mkdir(parents=True)
    installer.marker.write_text("[1, 2")
    assert not Installer(installer.source, installer.ha_config, installer.data).pending_restart
