"""Configuration and protocol constants."""

DOMAIN = "philips_skylight"
VERSION = "0.3.4"
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
# The remote's icons and color dots, and its button order. EFFECTS keeps protocol order.
EFFECT_STYLE = {
    "Auto rhythm": ("mdi:sun-clock-outline", "purple"),
    "Refresh": ("mdi:weather-sunset-up", "blue"),
    "Energize": ("mdi:lightning-bolt", "light-blue"),
    "Focus": ("mdi:crosshairs-gps", "amber"),
    "Relax": ("mdi:sofa-outline", "orange"),
    "Rest": ("mdi:power-sleep", "deep-orange"),
}
# The remote repeats a held dim button about every 0.6 seconds.
HOLD_INTERVAL = 0.6
DIM_ICONS = {"dim_down": "mdi:brightness-4", "dim_up": "mdi:brightness-7"}
# Sets the current time as the start of the Auto rhythm schedule. Not a mode.
RHYTHM_START = "set_rhythm_start"
# Reserved before use and retained independently of config-entry removal.
STORAGE_KEY = f"{DOMAIN}.sequence_7ffe"
SEQUENCE_BLOCK = 256
# Recovery jump after a lost or restored Store: about 1 million commands, 1/16 of the space.
SEQUENCE_SKIP = 0x100000
# A pairing or unpair-all request repeats for this long, like the remote's 10-second
# hold. A much longer stream of requests makes the panel drop the other remote.
PAIRING_BURST = 10
# The remote sends its pairing request about twice a second while the button is held.
PAIRING_RATE = 2
# Keep the recorded power and mode if the proxy comes back within this many seconds.
OUTAGE_GRACE = 60
