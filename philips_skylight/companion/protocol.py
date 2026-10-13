"""The captured, unsegmented Bluetooth Mesh access messages.

This intentionally is not a provisioning client or a general mesh stack. The
factory mesh has fixed keys and IV index; only captured commands are emitted.
"""

from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from cryptography.hazmat.primitives.cmac import CMAC

from .const import (
    APPLICATION_KEY,
    DESTINATION,
    EFFECTS,
    IV_INDEX,
    NETWORK_KEY,
    RHYTHM_START,
    SOURCE,
    UNPAIR_CODES,
)


def cmac(key: bytes, message: bytes) -> bytes:
    cipher = CMAC(algorithms.AES(key))
    cipher.update(message)
    return cipher.finalize()


def s1(message: bytes) -> bytes:
    return cmac(bytes(16), message)


def k2(key: bytes, p: bytes = b"\x00") -> tuple[int, bytes, bytes]:
    t = cmac(s1(b"smk2"), key)
    t1 = cmac(t, p + b"\x01")
    t2 = cmac(t, t1 + p + b"\x02")
    t3 = cmac(t, t2 + p + b"\x03")
    return t1[-1] & 0x7F, t2, t3


def k3(key: bytes) -> bytes:
    return cmac(cmac(s1(b"smk3"), key), b"id64\x01")[-8:]


def k4(key: bytes) -> int:
    return cmac(cmac(s1(b"smk4"), key), b"id6\x01")[-1] & 0x3F


def _aes(key: bytes, block: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    return cipher.update(block) + cipher.finalize()


@dataclass(frozen=True)
class MeshMessage:
    source: int
    destination: int
    sequence: int
    ttl: int
    payload: bytes


class MeshCodec:
    def __init__(self) -> None:
        self.nid, self.encryption_key, self.privacy_key = k2(NETWORK_KEY)
        self.aid = k4(APPLICATION_KEY)

    def encode(self, payload: bytes, sequence: int) -> bytes:
        """Return a complete advertising data structure (length, 0x2A, PDU)."""
        if not 0 <= sequence <= 0xFFFFFF:
            raise ValueError("Mesh sequence exhausted; never wrap or reset it")
        if not 1 <= len(payload) <= 11:
            raise ValueError("Only unsegmented access payloads up to 11 bytes are supported")
        seq = sequence.to_bytes(3, "big")
        src = SOURCE.to_bytes(2, "big")
        dst = DESTINATION.to_bytes(2, "big")
        iv = IV_INDEX.to_bytes(4, "big")
        header = b"\x05" + seq + src  # CTL=0, TTL=5
        app_nonce = b"\x01\x00" + seq + src + dst + iv
        upper = AESCCM(APPLICATION_KEY, tag_length=4).encrypt(app_nonce, payload, None)
        lower = bytes([0x40 | self.aid]) + upper  # SEG=0, AKF=1
        network_nonce = b"\x00" + header + b"\x00\x00" + iv
        encrypted = AESCCM(self.encryption_key, tag_length=4).encrypt(
            network_nonce, dst + lower, None
        )
        privacy = _aes(self.privacy_key, bytes(5) + iv + encrypted[:7])[:6]
        obfuscated = bytes(a ^ b for a, b in zip(header, privacy, strict=True))
        pdu = bytes([((IV_INDEX & 1) << 7) | self.nid]) + obfuscated + encrypted
        return bytes([len(pdu) + 1, 0x2A]) + pdu

    def decode(self, advertisement: bytes) -> list[MeshMessage]:
        """Authenticate each mesh AD structure; ignore unrelated/malformed traffic."""
        messages = []
        offset = 0
        while offset < len(advertisement):
            length = advertisement[offset]
            end = offset + length + 1
            if length == 0 or end > len(advertisement):
                break
            if advertisement[offset + 1] == 0x2A:
                message = self._decode_pdu(advertisement[offset + 2 : end])
                if message is not None:
                    messages.append(message)
            offset = end
        return messages

    def _decode_pdu(self, pdu: bytes) -> MeshMessage | None:
        if len(pdu) < 18 or pdu[0] != ((IV_INDEX & 1) << 7) | self.nid:
            return None
        encrypted = pdu[7:]
        iv = IV_INDEX.to_bytes(4, "big")
        privacy = _aes(self.privacy_key, bytes(5) + iv + encrypted[:7])[:6]
        header = bytes(a ^ b for a, b in zip(pdu[1:7], privacy, strict=True))
        if header[0] & 0x80:  # control messages are not access commands
            return None
        try:
            network_nonce = b"\x00" + header + b"\x00\x00" + iv
            decoded = AESCCM(self.encryption_key, tag_length=4).decrypt(
                network_nonce, encrypted, None
            )
            if len(decoded) < 8 or decoded[2] != 0x40 | self.aid:
                return None
            app_nonce = b"\x01\x00" + header[1:6] + decoded[:2] + iv
            payload = AESCCM(APPLICATION_KEY, tag_length=4).decrypt(app_nonce, decoded[3:], None)
        except (InvalidTag, ValueError):
            return None
        return MeshMessage(
            int.from_bytes(header[4:6], "big"),
            int.from_bytes(decoded[:2], "big"),
            int.from_bytes(header[1:4], "big"),
            header[0] & 0x7F,
            payload,
        )


def command_payload(command: str, transaction: int) -> bytes:
    if not 0x80 <= transaction <= 0xFF:
        raise ValueError("Transaction must be in the remote's 0x80..0xFF range")
    if command == "toggle":
        return bytes([0xC8, 0x11, 0x02, transaction, 0x03, 0x01, 0x41])
    if command in ("dim_down", "dim_up"):
        return bytes([0xC8, 0x11, 0x02, transaction, 0x01, command == "dim_up", 0x14, 0x41])
    if command in EFFECTS:
        return bytes([0xC9, 0x11, 0x02, transaction, 0x04, 0xFF, EFFECTS.index(command) + 1, 0x41])
    if command == RHYTHM_START:
        # The remote sends this while Auto rhythm and Relax are held together.
        return bytes([0xE0, 0x11, 0x02, transaction, 0x00])
    raise ValueError(f"Unsupported command: {command}")


def pairing_payload(transaction: int) -> bytes:
    """Captured vendor pairing request; panel acceptance is still unverified."""
    if not 0x80 <= transaction <= 0xFF:
        raise ValueError("Transaction must be in the remote's 0x80..0xFF range")
    return bytes([0xCF, 0x11, 0x02, transaction, 0x01]) + b"\x11" * 6


def unpair_payload(transaction: int, code: int) -> bytes:
    """Experimental: the pairing request with a guessed sub-command byte instead of 0x01."""
    if not 0x80 <= transaction <= 0xFF:
        raise ValueError("Transaction must be in the remote's 0x80..0xFF range")
    if code not in UNPAIR_CODES:
        raise ValueError(f"Unsupported unpair code: {code}")
    return bytes([0xCF, 0x11, 0x02, transaction, code]) + b"\x11" * 6


def identify_command(payload: bytes) -> str | None:
    if len(payload) < 4 or not 0x80 <= payload[3] <= 0xFF:
        return None
    for command in ("toggle", "dim_down", "dim_up", *EFFECTS, RHYTHM_START):
        if payload == command_payload(command, payload[3]):
            return command
    if (
        len(payload) == 8
        and payload[:3] == b"\xc8\x11\x02"
        and payload[4:] in (b"\x01\x02\x14\x41", b"\x01\x03\x14\x41")
    ):
        return "dim_up" if payload[5] == 3 else "dim_down"
    return None
