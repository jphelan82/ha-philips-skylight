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
            r"^[ \t]+name:[ \t]*['\"]?([A-Za-z0-9_${}-]+)['\"]?[ \t]*(?:#.*)?$", match[1], re.M
        )
        if name:
            names = _substitutions(text)
            value = re.sub(r"\$\{?(\w+)\}?", lambda m: names.get(m[1], m[0]), name[1])
            if "$" not in value:
                return value
    return fallback


def _substitutions(text):
    match = re.search(r"^substitutions:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    if not match:
        return {}
    return {
        key: value
        for key, value in re.findall(
            r"^[ \t]+([A-Za-z0-9_]+):[ \t]*['\"]?([^'\"\n#]*?)['\"]?[ \t]*(?:#.*)?$", match[1], re.M
        )
    }


def friendly_name(text):
    """The node's friendly name, which Home Assistant shows as its title, or None."""
    match = re.search(r"^esphome:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    if not match:
        return None
    found = re.search(
        r"^[ \t]+friendly_name:[ \t]*['\"]?([^'\"\n#]+?)['\"]?[ \t]*(?:#.*)?$", match[1], re.M
    )
    if not found:
        return None
    value = found[1]
    names = _substitutions(text)
    value = re.sub(r"\$\{?(\w+)\}?", lambda m: names.get(m[1], m[0]), value)
    return None if "$" in value else value


def has_api_key(text):
    """Whether the node YAML gives its ESPHome API an encryption key."""
    match = re.search(r"^api:[^\n]*\n((?:[ \t]+[^\n]*\n?|\n)*)", text, re.M)
    return bool(match and re.search(r"^[ \t]+encryption:", match[1], re.M))


def has_skylight(text):
    """Whether a node YAML already has the package line or a hand-made setup."""
    return PACKAGE in text or re.search(r"^ble_adv_proxy:", text, re.M) is not None


def list_nodes(folder: Path, proxies=frozenset()):
    """ESPHome node files in the folder that are Bluetooth proxies.

    A node counts if its YAML has a bluetooth_proxy section, or if its name is in
    `proxies`: the devices Home Assistant uses as Bluetooth proxies. Ready-made
    firmware turns the proxy on in a package from GitHub, so its YAML may not say so.
    """
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
        name = _node_name(text, path.stem)
        if not re.search(r"^bluetooth_proxy:", text, re.M) and name not in proxies:
            continue
        nodes.append(
            {
                "file": path.name,
                "node": name,
                "friendly_name": friendly_name(text),
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


def _build_files(component: Path):
    """The component files the proxy builds from, as tools/firmware.lock counts them.

    The README, the license and Python caches do not change the firmware.
    """
    return [
        item.relative_to(component)
        for item in component.rglob("*")
        if item.is_file()
        and item.name not in ("README.md", "LICENSE")
        and "__pycache__" not in item.relative_to(component).parts
        and item.suffix != ".pyc"
    ]


def _component_differs(folder: Path, firmware: Path):
    component, source = folder / COMPONENT, firmware / COMPONENT
    return any(
        not (component / name).is_file()
        or (component / name).read_bytes() != (source / name).read_bytes()
        for name in _build_files(source)
    )


def _differs(folder: Path, firmware: Path):
    """Whether the copies in the ESPHome folder differ from the add-on's firmware files."""
    package = folder / PACKAGE
    if not package.is_file() or package.read_bytes() != (firmware / PACKAGE).read_bytes():
        return True
    return _component_differs(folder, firmware)


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
    if component.exists() and _component_differs(folder, firmware):
        backups.append(f"ble_adv_proxy.bak-{stamp}")
        shutil.copytree(component, folder / backups[-1])
    component.parent.mkdir(exist_ok=True)
    shutil.copytree(source, component, dirs_exist_ok=True)
    return backups


def update_files(folder: Path, firmware: Path, proxies=frozenset()):
    """Bring the shared firmware files up to date. The node YAML files stay as they are.

    `proxies` is the same set of node names that list_nodes takes.
    """
    if not any(node["uses_package"] for node in list_nodes(folder, proxies)):
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
        first = re.search(r"^[ \t]*([^ \t\n#])", rest, re.M)
        if first and first[1] == "-":
            # A mapping entry inside a YAML list makes the file invalid.
            raise ValueError(
                "This node's packages setting is a list. Use Install the firmware by hand, "
                f"and add '- !include {PACKAGE}' to that list."
            )
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


def install_package(folder: Path, firmware: Path, file: str, proxies=frozenset()):
    """Copy the package beside the node YAML and add its entry. Return what changed.

    `proxies` is the same set of node names that list_nodes takes.
    """
    if file not in {node["file"] for node in list_nodes(folder, proxies)}:
        raise ValueError("Choose one of the Bluetooth proxies listed")
    node = folder / file
    if folder.is_symlink() or node.is_symlink():
        raise ValueError("Refusing to change files through a symbolic link")
    text = node.read_text()
    updated = add_package_line(text)  # Raises before any file changes.
    stamp = _stamp()
    _copy_files(folder, firmware, stamp)
    backup = None
    if updated != text:
        backup = f"{file}.bak-{stamp}"
        shutil.copy2(node, folder / backup)
        _write_atomic(node, updated)
    return {"file": file, "changed": updated != text, "backup": backup}
