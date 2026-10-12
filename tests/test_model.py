from dataclasses import replace

from custom_components.philips_skylight.model import AssumedState, RemoteTracker
from custom_components.philips_skylight.protocol import MeshMessage, command_payload


def test_toggle_does_not_invent_initial_state_or_scene_power():
    state = AssumedState()
    state.apply("toggle")
    assert state.is_on is None
    state.apply("Focus")
    assert state.effect == "Focus"
    assert state.is_on is None
    state.is_on = True
    state.apply("toggle")
    assert state.is_on is False


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
