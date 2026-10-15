"""Install only the bundled integration, preserving HA-managed storage."""

import json
import logging
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from . import DOMAIN

LOG = logging.getLogger(__name__)


def _version(text):
    return tuple(int(n) for n in text.split("."))


class Installer:
    def __init__(self, source: Path, ha_config: Path, data: Path):
        self.source = source
        self.ha_config = ha_config
        self.data = data
        self.target = ha_config / "custom_components" / DOMAIN
        self.version = json.loads((source / "manifest.json").read_text())["version"]
        self.marker = data / "installation.json"
        self.pending_restart = False
        # The last install error, for the page. Startup keeps running without the install.
        self.error = None
        if self.marker.exists():
            try:
                self.pending_restart = bool(
                    json.loads(self.marker.read_text()).get("pending_restart")
                )
            except (ValueError, AttributeError, OSError):
                LOG.warning("Cannot read %s; the integration version check still runs", self.marker)

    def installed(self) -> bool:
        return (self.target / "manifest.json").is_file()

    def _save_marker(self):
        self.data.mkdir(parents=True, exist_ok=True)
        staging = self.marker.with_suffix(".tmp")
        with staging.open("w") as file:
            json.dump({"version": self.version, "pending_restart": self.pending_restart}, file)
            file.flush()
            os.fsync(file.fileno())
        os.replace(staging, self.marker)

    def mark_restarted(self):
        self.pending_restart = False
        self._save_marker()

    def install(self) -> bool:
        """Return whether files changed. Keep the error for the page if it fails."""
        try:
            changed = self._install()
        except Exception as err:
            self.error = f"The integration was not installed: {err}"[:300]
            raise
        self.error = None
        return changed

    def _install(self) -> bool:
        """Return whether files changed. Never restart HA or touch .storage."""
        parent = self.target.parent
        if parent.is_symlink() or self.target.is_symlink():
            raise ValueError("Refusing to install through a symbolic link")
        old = parent / f".{DOMAIN}-previous"
        if not self.target.exists() and old.is_dir() and not old.is_symlink():
            # An earlier install stopped between its two renames. Put the old version back.
            os.replace(old, self.target)
        files = [p for p in self.source.rglob("*") if p.is_file()]
        # A folder without manifest.json is incomplete. It is replaced, with a backup.
        manifest_file = self.target / "manifest.json"
        if manifest_file.is_file():
            try:
                manifest = json.loads(manifest_file.read_text())
            except ValueError as err:
                raise ValueError("The installed integration's manifest.json is damaged") from err
            if not isinstance(manifest, dict) or manifest.get("domain") != DOMAIN:
                raise ValueError("Existing directory is not the Skylight integration")
            try:
                installed_version = _version(manifest["version"])
            except (ValueError, KeyError, AttributeError) as err:
                raise ValueError("Cannot read the installed integration's version") from err
            if installed_version > _version(self.version):
                return False  # HACS/manual updates remain authoritative; never downgrade.
        if self.target.exists() and all(
            (self.target / p.relative_to(self.source)).is_file()
            and (self.target / p.relative_to(self.source)).read_bytes() == p.read_bytes()
            for p in files
        ):
            return False
        parent.mkdir(parents=True, exist_ok=True)
        self.data.mkdir(parents=True, exist_ok=True)
        backup = None
        if self.target.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            backup = self.data / "backups" / stamp
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.target, backup, ignore=shutil.ignore_patterns("__pycache__"))
        staging = Path(tempfile.mkdtemp(prefix=f".{DOMAIN}-", dir=parent))
        if old.exists():
            shutil.rmtree(staging)
            raise ValueError("Previous installation was interrupted; recover it before updating")
        try:
            shutil.copytree(self.source, staging, dirs_exist_ok=True)
            if self.target.exists():
                os.replace(self.target, old)
            try:
                os.replace(staging, self.target)
            except BaseException:
                if old.exists():
                    os.replace(old, self.target)
                raise
            self.pending_restart = True
            self._save_marker()
            if old.exists():
                shutil.rmtree(old)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return True
