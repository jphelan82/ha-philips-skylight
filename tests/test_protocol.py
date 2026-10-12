"""Compare mesh crypto against real remote captures, not just self-round-trips."""

import re
from pathlib import Path

import pytest

from custom_components.philips_skylight.const import APPLICATION_KEY, EFFECTS, NETWORK_KEY
from custom_components.philips_skylight.protocol import (
    MeshCodec,
    command_payload,
    identify_command,
    k3,
    k4,
    pairing_payload,
)

CAPTURE = Path(__file__).resolve().parents[1] / "tools/capture-2026-10-12.log"
FIRST_TOGGLE = bytes.fromhex("1a2a1bc5e03c8aceab4468d9d8e76f77efbb889cd1530fa6955cac")


def test_factory_keys_and_captured_toggle():
    assert k3(NETWORK_KEY).hex() == "c7cd5342d1544cd5"
    assert k4(APPLICATION_KEY) == 0x38
    (message,) = MeshCodec().decode(FIRST_TOGGLE)
    assert (message.source, message.destination, message.sequence, message.ttl) == (
        0x7FFF,
        0xFFFF,
        17,
        5,
    )
    assert message.payload.hex() == "c8110288030141"


def test_encoder_reproduces_real_remote_packet(monkeypatch):
    monkeypatch.setattr("custom_components.philips_skylight.protocol.SOURCE", 0x7FFF)
    assert MeshCodec().encode(bytes.fromhex("c8110288030141"), 17) == FIRST_TOGGLE


def test_pairing_payload_matches_capture_and_fits_advertising_bearer():
    codec = MeshCodec()
    paired = []
    for line in CAPTURE.read_text().splitlines():
        raw = bytes.fromhex(re.search(r"raw=(\w+)", line)[1])
        for message in codec.decode(raw):
            if message.payload[0] == 0xCF:
                assert message.payload == pairing_payload(message.payload[3])
                paired.append(message)
    assert len(paired) == 13
    raw = codec.encode(pairing_payload(0x80), 100)
    assert len(raw) == 31
    (message,) = codec.decode(raw)
    assert message.source == 0x7FFE
    assert message.payload == pairing_payload(0x80)
    assert identify_command(message.payload) is None


def test_all_capture_mesh_pdus_authenticate():
    codec = MeshCodec()
    decoded = []
    for line in CAPTURE.read_text().splitlines():
        raw = bytes.fromhex(re.search(r"raw=(\w+)", line)[1])
        if raw[1] != 0x2A:
            continue
        messages = codec.decode(raw)
        assert len(messages) == 1, line
        assert messages[0].source == 0x7FFF
        decoded.extend(messages)
    assert len(decoded) > 40
    commands = {identify_command(message.payload) for message in decoded}
    assert {"toggle", "dim_down", "dim_up", *EFFECTS} <= commands


@pytest.mark.parametrize("command", ["toggle", "dim_up", "dim_down", *EFFECTS])
def test_transmitted_packets_have_own_sender_and_fit_legacy_advertisements(command):
    codec = MeshCodec()
    packet = codec.encode(command_payload(command, 0x80), 0x123456)
    assert len(packet) <= 31
    (message,) = codec.decode(packet)
    assert message.source == 0x7FFE
    assert message.sequence == 0x123456
    assert identify_command(message.payload) == command


def test_tampered_truncated_and_unrelated_advertisements_are_ignored():
    codec = MeshCodec()
    for index in range(2, len(FIRST_TOGGLE)):
        packet = bytearray(FIRST_TOGGLE)
        packet[index] ^= 1
        assert codec.decode(bytes(packet)) == []
    for length in range(len(FIRST_TOGGLE)):
        assert codec.decode(FIRST_TOGGLE[:length]) == []
    assert len(codec.decode(b"\x02\x01\x06" + FIRST_TOGGLE)) == 1
    assert codec.decode(bytes.fromhex("03032718")) == []


def test_encoder_rejects_sequence_wrap_segmentation_and_unsupported_commands():
    codec = MeshCodec()
    for seq in (-1, 0x1000000):
        with pytest.raises(ValueError):
            codec.encode(command_payload("toggle", 0x80), seq)
    with pytest.raises(ValueError):
        codec.encode(bytes(12), 1)
    for command in ("on", "off", "pair", "brightness"):
        with pytest.raises(ValueError):
            command_payload(command, 0x80)
