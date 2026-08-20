from lifeplanner_core.event_bus import FileEventBus, LifePlannerEvent


def test_event_bus_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("LIFEPLANNER_DATA_DIR", str(tmp_path))
    bus = FileEventBus("default")
    event = LifePlannerEvent.create("finance.proposal.created", "fpm", "default", {"amount": 12.5})
    bus.publish(event)
    events, offset = bus.read_since(0)
    assert events == [event]
    assert offset > 0
    again, same_offset = bus.read_since(offset)
    assert again == []
    assert same_offset == offset
