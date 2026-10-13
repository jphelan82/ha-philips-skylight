"""Find ESPHome Bluetooth proxies and add the Skylight package to one, with a backup."""

import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PACKAGE = "skylight-transmitter.yaml"
COMPONENT = Path("components") / "ble_adv_proxy"
PACKAGE_LINE = f"skylight: !include {PACKAGE}"
SKIP = {"secrets.yaml", PACKAGE}


def _stamp():
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


def _node_name(text, fallback):
    match = re.search(r"^esphome:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    if match:
        name = re.search(
            r"^[ \t]+name:[ \t]*['\"]?([A-Za-z0-9_-]+)['\"]?[ \t]*(?:#.*)?$", match[1], re.M
        )
        if name:
            return name[1]
    return fallback


def has_api_key(text):
    """Whether the node YAML gives its ESPHome API an encryption key."""
    match = re.search(r"^api:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    return bool(match and re.search(r"^[ \t]+encryption:", match[1], re.M))


def has_skylight(text):
    """Whether a node YAML already has the package line or a hand-made setup."""
    return PACKAGE in text or re.search(r"^ble_adv_proxy:", text, re.M) is not None


def list_nodes(folder: Path):
    """ESPHome node files in the folder that are Bluetooth proxies."""
    if not folder.is_dir():
        return []
    nodes = []
    for path in sorted(folder.glob("*.yaml")):
        if path.name in SKIP or path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if not re.search(r"^bluetooth_proxy:", text, re.M):
            continue
        nodes.append(
            {
                "file": path.name,
                "node": _node_name(text, path.stem),
                "has_skylight": has_skylight(text),
                # Only nodes that include the package get firmware updates from the add-on.
                "uses_package": PACKAGE in text,
                # Without a key, any device on the network can make the proxy send.
                "api_key": has_api_key(text),
            }
        )
    return nodes


def firmware_version(text):
    """The skylight_firmware number in a package's text, or None."""
    match = re.search(r'^[ \t]+skylight_firmware:[ \t]*["\']?(\d+)["\']?', text, re.M)
    return match[1] if match else None


def _differs(folder: Path, firmware: Path):
    """Whether the copies in the ESPHome folder differ from the add-on's firmware files."""
    package = folder / PACKAGE
    if not package.is_file() or package.read_bytes() != (firmware / PACKAGE).read_bytes():
        return True
    component = folder / COMPONENT
    return any(
        not (component / item.name).is_file()
        or (component / item.name).read_bytes() != item.read_bytes()
        for item in (firmware / COMPONENT).iterdir()
        if item.is_file()
    )


def files_current(folder: Path, firmware: Path):
    return not _differs(folder, firmware)


def _copy_files(folder: Path, firmware: Path, stamp: str):
    """Copy the package and the component into the ESPHome folder, keeping backups."""
    package, component = folder / PACKAGE, folder / COMPONENT
    if folder.is_symlink() or package.is_symlink() or component.is_symlink():
        raise ValueError("Refusing to change files through a symbolic link")
    backups = []
    if package.is_file() and package.read_bytes() != (firmware / PACKAGE).read_bytes():
        backups.append(f"{PACKAGE}.bak-{stamp}")
        shutil.copy2(package, folder / backups[-1])
    shutil.copyfile(firmware / PACKAGE, package)
    source = firmware / COMPONENT
    if component.exists() and any(
        not (component / item.name).is_file()
        or (component / item.name).read_bytes() != item.read_bytes()
        for item in source.iterdir()
    ):
        backups.append(f"ble_adv_proxy.bak-{stamp}")
        shutil.copytree(component, folder / backups[-1])
    component.parent.mkdir(exist_ok=True)
    shutil.copytree(source, component, dirs_exist_ok=True)
    return backups


def update_files(folder: Path, firmware: Path):
    """Bring the shared firmware files up to date. The node YAML files stay as they are."""
    if not any(node["uses_package"] for node in list_nodes(folder)):
        raise ValueError("No Bluetooth proxy uses the Skylight firmware package")
    if files_current(folder, firmware):
        return {"changed": False, "backups": []}
    return {"changed": True, "backups": _copy_files(folder, firmware, _stamp())}


def add_package_line(text):
    """Return the node YAML with the Skylight package entry added."""
    if has_skylight(text):
        return text
    match = re.search(r"^packages:[ \t]*(?:#[^\n]*)?$", text, re.M)
    if match:
        rest = text[match.end() :]
        indent = re.match(r"\n([ \t]+)\S", rest)
        prefix = indent[1] if indent else "  "
        return text[: match.end()] + f"\n{prefix}{PACKAGE_LINE}" + rest
    if re.search(r"^packages:", text, re.M):
        # An inline value such as !include_dir_named cannot take one more entry safely.
        raise ValueError(
            f"This node's packages setting is not a plain list. Add '{PACKAGE_LINE}' by hand."
        )
    return text.rstrip("\n") + f"\n\npackages:\n  {PACKAGE_LINE}\n"


def _write_atomic(path: Path, text: str):
    handle, staging = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(handle, "w") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        shutil.copymode(path, staging)
        os.replace(staging, path)
    except BaseException:
        Path(staging).unlink(missing_ok=True)
        raise


def install_package(folder: Path, firmware: Path, file: str):
    """Copy the package beside the node YAML and add its entry. Return what changed."""
    if file not in {node["file"] for node in list_nodes(folder)}:
        raise ValueError("Choose one of the Bluetooth proxies listed")
    node = folder / file
    if folder.is_symlink() or node.is_symlink():
        raise ValueError("Refusing to change files through a symbolic link")
    stamp = _stamp()
    _copy_files(folder, firmware, stamp)
    text = node.read_text()
    updated = add_package_line(text)
    backup = None
    if updated != text:
        backup = f"{file}.bak-{stamp}"
        shutil.copy2(node, folder / backup)
        _write_atomic(node, updated)
    return {"file": file, "changed": updated != text, "backup": backup}
