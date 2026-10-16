"""Supervisor add-on for the native Philips Skylight integration."""

VERSION = "0.6.0"
DOMAIN = "philips_skylight"
# Mirrors the integration's const.EFFECTS; tests/test_integration.py checks parity.
EFFECTS = ("Refresh", "Energize", "Focus", "Relax", "Rest", "Auto rhythm")
UNIQUE_ID_PREFIX = "factory_mesh_7ffe_"


def slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def unique_id(name: str) -> str:
    """Return the integration's registry unique ID for a command or entity name."""
    return UNIQUE_ID_PREFIX + slug(name)
