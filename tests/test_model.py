from dataclasses import replace

import pytest

from custom_components.philips_skylight.const import EFFECTS
from custom_components.philips_skylight.model import AssumedState, RemoteTracker
from custom_components.philips_skylight.protocol import MeshMessage, command_payload


def test_toggle_does_not_invent_initial_state_but_a_scene_turns_the_panel_on():
    state = AssumedState()
    state.apply("toggle")
    assert state.is_on is None
    state.apply("dim_down")
    assert state.is_on is None
    state.apply("Focus")
    assert state.effect == "Focus"
    assert state.is_on is True
    state.apply("toggle")
    assert state.is_on is False
    state.apply("Relax")
    assert state.is_on is True
    assert state.effect == "Relax"


def test_relay_and_transaction_duplicates_do_not_double_toggle():
    tracker = RemoteTracker()
    remote = MeshMessage(0x7FFF, 0xFFFF, 10, 5, command_payload("toggle", 0x80))
    assert tracker.accept(remote, now=1) == "toggle"
    assert tracker.accept(replace(remote, ttl=4), now=1.1) is None
    assert tracker.accept(replace(remote, sequence=11), now=1.2) is None
    assert (
        tracker.accept(
            replace(remote, sequence=12, payload=command_payload("toggle", 0x81)), now=1.3
        )
        == "toggle"
    )


def test_holds_at_remote_cadence_and_filter_own_packets():
    tracker = RemoteTracker()
    remote = MeshMessage(0x7FFF, 0xFFFF, 10, 5, bytes.fromhex("c811028001031441"))
    assert tracker.accept(remote, now=1) == "dim_up"
    assert tracker.accept(replace(remote, sequence=11), now=1.6) == "dim_up"
    assert tracker.accept(replace(remote, source=0x7FFE), now=2) is None
    assert tracker.accept(replace(remote, destination=1), now=2) is None


@pytest.mark.parametrize("command", ["toggle", "dim_down", "dim_up", *EFFECTS])
def test_other_remote_sources_update_all_stored_state(command):
    tracker = RemoteTracker()
    state = AssumedState(is_on=True, effect="Focus")
    remote = MeshMessage(0x1234, 0xFFFF, 10, 5, command_payload(command, 0x80))
    accepted = tracker.accept(remote, now=1)
    assert accepted == command
    state.apply(accepted)
    assert state.last_command == command
    assert state.is_on is (command != "toggle")
    assert state.effect == (command if command in EFFECTS else "Focus")
    assert tracker.accept(replace(remote, ttl=4), now=1.1) is None


def test_two_remotes_can_use_same_transaction_and_sequence_without_suppressing_each_other():
    tracker = RemoteTracker()
    remote = MeshMessage(0x7FFF, 0xFFFF, 10, 5, command_payload("toggle", 0x80))
    assert tracker.accept(remote, now=1) == "toggle"
    assert tracker.accept(replace(remote, source=0x1234), now=1.1) == "toggle"
    # Interleaving a different remote must not hide a retransmission of the first.
    assert tracker.accept(replace(remote, sequence=11), now=1.2) is None


def test_interleaved_buttons_do_not_reset_transaction_filter():
    tracker = RemoteTracker()
    remote = MeshMessage(0x7FFF, 0xFFFF, 10, 5, command_payload("toggle", 0x80))
    assert tracker.accept(remote, now=1) == "toggle"
    assert tracker.accept(
        replace(remote, sequence=11, payload=command_payload("Focus", 0x81)), now=1.1
    ) == "Focus"
    assert tracker.accept(replace(remote, sequence=12), now=1.2) is None


@pytest.mark.parametrize("source", [0, 0x7FFE, 0x8000, 0xFFFF])
def test_own_and_invalid_sender_addresses_are_ignored(source):
    remote = MeshMessage(source, 0xFFFF, 10, 5, command_payload("toggle", 0x80))
    assert RemoteTracker().accept(remote) is None
