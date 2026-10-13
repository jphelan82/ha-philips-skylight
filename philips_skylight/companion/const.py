"""Configuration and protocol constants."""

DOMAIN = "philips_skylight"
VERSION = "0.2.8"
CONF_TRANSMIT_SERVICE = "transmit_service"
CONF_PROXY_ENTITY = "proxy_entity"
RECEIVE_EVENT = "esphome.ble_adv.raw_adv"
SOURCE = 0x7FFE
REMOTE_SOURCE = 0x7FFF
DESTINATION = 0xFFFF
NETWORK_KEY = bytes.fromhex("11" * 16)
APPLICATION_KEY = bytes(16)
IV_INDEX = 0
EFFECTS = ("Refresh", "Energize", "Focus", "Relax", "Rest", "Auto rhythm")
# Sets the current time as the start of the Auto rhythm schedule. Not a mode.
RHYTHM_START = "set_rhythm_start"
# Reserved before use and retained independently of config-entry removal.
STORAGE_KEY = f"{DOMAIN}.sequence_7ffe"
SEQUENCE_BLOCK = 256
# Recovery jump after a lost or restored Store: about 1 million commands, 1/16 of the space.
SEQUENCE_SKIP = 0x100000
# Keep the recorded power and mode if the proxy comes back within this many seconds.
OUTAGE_GRACE = 60
