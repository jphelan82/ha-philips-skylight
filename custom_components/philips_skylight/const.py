"""Configuration and protocol constants."""

DOMAIN = "philips_skylight"
VERSION = "0.2.2"
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
# Reserved before use and retained independently of config-entry removal.
STORAGE_KEY = f"{DOMAIN}.sequence_7ffe"
SEQUENCE_BLOCK = 256
