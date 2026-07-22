import math

from streaming.live_inference import live_probabilities
from streaming.producers.match_poller import envelope


def test_envelope_message_id_is_idempotent():
    first = envelope(1, {"x": 2}, observed_at="2026-01-01T00:00:00+00:00")
    second = envelope(1, {"x": 2}, observed_at="2026-01-02T00:00:00+00:00")
    assert first["message_id"] == second["message_id"]


def test_live_probabilities_are_normalized():
    probabilities = live_probabilities(1, 0, 60)
    assert math.isclose(sum(probabilities.values()), 1)
