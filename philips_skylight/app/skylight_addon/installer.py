"""Install only the bundled integration, preserving HA-managed storage."""

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from . import DOMAIN


class Installer:
    def __init__(self, source: Path, ha_config: Path, data: Path):
        self.source = source
        self.ha_config = ha_config
        self.data = data
        self.target = ha_config / "custom_components" / DOMAIN
        self.version = json.loads((source / "manifest.json").read_text())["version"]
        self.marker = data / "installation.json"
        self.pending_restart = False
        if self.marker.exists():
            self.pending_restart = bool(json.loads(self.marker.read_text()).get("pending_restart"))

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
        """Return whether files changed. Never restart HA or touch .storage."""
        parent = self.target.parent
        if parent.is_symlink() or self.target.is_symlink():
            raise ValueError("Refusing to install through a symbolic link")
        files = [p for p in self.source.rglob("*") if p.is_file()]
        if self.target.exists():
            manifest = json.loads((self.target / "manifest.json").read_text())
            if manifest.get("domain") != DOMAIN:
                raise ValueError("Existing directory is not the Skylight integration")
            installed_version = tuple(int(n) for n in manifest["version"].split("."))
            bundled_version = tuple(int(n) for n in self.version.split("."))
            if installed_version > bundled_version:
                return False  # HACS/manual updates remain authoritative; never downgrade.
            if all(
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
        old = parent / f".{DOMAIN}-previous"
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
