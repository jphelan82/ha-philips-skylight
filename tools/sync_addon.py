"""Bundle canonical integration and firmware sources into the add-on build context."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from dashboard_card import generated_files

ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    (ROOT / "custom_components/philips_skylight", ROOT / "philips_skylight/companion"),
    (ROOT / "esphome", ROOT / "philips_skylight/firmware"),
)

FIRMWARE = ROOT / "esphome"
FIRMWARE_LOCK = ROOT / "tools/firmware.lock"


def firmware_version(text):
    match = re.search(r'^  skylight_firmware: "(\d+)"$', text, re.M)
    if not match:
        raise SystemExit("esphome/skylight-transmitter.yaml has no skylight_firmware number")
    return match[1]


def firmware_lock():
    """The firmware's version number and a hash of every file the proxy builds from."""
    # The same file set that the bundle copies, so caches such as __pycache__ never count.
    files = [FIRMWARE / "skylight-transmitter.yaml"] + sorted(
        file
        for file in sources(FIRMWARE / "components/ble_adv_proxy").values()
        if file.name not in ("README.md", "LICENSE")
    )
    digest = hashlib.sha256()
    for file in files:
        digest.update(str(file.relative_to(FIRMWARE)).encode() + b"\0" + file.read_bytes())
    version = firmware_version(files[0].read_text())
    return {"version": version, "sha256": digest.hexdigest()}


def check_firmware(write):
    current = firmware_lock()
    locked = json.loads(FIRMWARE_LOCK.read_text()) if FIRMWARE_LOCK.exists() else None
    if current == locked:
        return
    if locked and current["version"] == locked["version"]:
        raise SystemExit(
            "The firmware changed. Raise skylight_firmware in "
            "esphome/skylight-transmitter.yaml, then run tools/sync_addon.py again."
        )
    if not write:
        raise SystemExit("tools/firmware.lock is out of date. Run tools/sync_addon.py.")
    FIRMWARE_LOCK.write_text(json.dumps(current, indent=2) + "\n")


def sources(path):
    return {
        file.relative_to(path): file
        for file in path.rglob("*")
        if file.is_file()
        and "__pycache__" not in file.parts
        and ".esphome" not in file.parts
        and file.name != "secrets.yaml"
        and file.suffix != ".pyc"
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check_firmware(write=not args.check)
    for path, content in generated_files().items():
        if args.check:
            if path.read_text() != content:
                raise SystemExit(f"Dashboard card differs from its generator: {path.name}")
        else:
            path.write_text(content)
    for source, destination in PAIRS:
        files = sources(source)
        if args.check:
            bundled = sources(destination)
            if files.keys() != bundled.keys() or any(
                file.read_bytes() != bundled[name].read_bytes() for name, file in files.items()
            ):
                raise SystemExit(f"Bundle differs from canonical source: {destination}")
        else:
            if destination.exists():
                shutil.rmtree(destination)
            for name, file in files.items():
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)


if __name__ == "__main__":
    main()
