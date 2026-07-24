from types import SimpleNamespace

import pytest

from world_cup_intelligence.inference import PredictionService
from world_cup_intelligence.prematch import (
    PrematchLookupError,
    event_from_payload,
    fetch_sofascore_event,
    parse_sofascore_event_id,
)


def test_parse_sofascore_public_match_link():
    url = "https://www.sofascore.com/football/match/canada-mexico/abc#id:12345678"
    assert parse_sofascore_event_id(url) == 12345678


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/football/match/x#id:12345678",
        "https://www.sofascore.com/football/match/without-an-id",
        "not a url",
    ],
)
def test_reject_invalid_or_non_sofascore_links(url):
    with pytest.raises(PrematchLookupError):
        parse_sofascore_event_id(url)


def test_event_payload_builds_model_context():
    payload = {
        "event": {
            "id": 12345678,
            "startTimestamp": 1783278000,
            "homeTeam": {"id": 4752, "name": "Canada", "ranking": 28},
            "awayTeam": {"id": 4781, "name": "Mexico", "ranking": 17},
            "tournament": {
                "name": "FIFA World Cup, Group A",
                "uniqueTournament": {"name": "FIFA World Cup"},
            },
            "roundInfo": {"name": "Group A"},
            "venue": {
                "name": "Example Stadium",
                "city": {"name": "Example City"},
                "country": {"name": "United States"},
            },
        }
    }
    event = event_from_payload(
        12345678,
        payload,
        home_country="Canada",
        away_country="Mexico",
    )
    assert event.competition_type == "world_cup"
    assert event.round_name == "Group A"
    assert event.venue_name == "Example Stadium"
    assert event.neutral_site == 1


def test_event_fetch_uses_api_host_and_xhr_header(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"event": {"id": 12345678}}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(
        "world_cup_intelligence.prematch.requests.get",
        fake_get,
    )

    assert fetch_sofascore_event(12345678)["event"]["id"] == 12345678
    assert calls[0][0] == "https://api.sofascore.com/api/v1/event/12345678"
    assert calls[0][1]["headers"]["x-requested-with"] == "XMLHttpRequest"


def test_event_fetch_falls_back_when_primary_host_is_forbidden(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        @staticmethod
        def json():
            return {"event": {"id": 12345678}}

    def fake_get(url, **_kwargs):
        calls.append(url)
        return Response(403 if len(calls) == 1 else 200)

    monkeypatch.setattr(
        "world_cup_intelligence.prematch.requests.get",
        fake_get,
    )

    assert fetch_sofascore_event(12345678)["event"]["id"] == 12345678
    assert calls == [
        "https://api.sofascore.com/api/v1/event/12345678",
        "https://www.sofascore.com/api/v1/event/12345678",
    ]


def test_link_prediction_uses_scraped_context(monkeypatch):
    payload = {
        "event": {
            "id": 99999999,
            "startTimestamp": 1814918400,
            "homeTeam": {"id": 4752, "name": "Canada", "ranking": 28},
            "awayTeam": {"id": 4781, "name": "Mexico", "ranking": 17},
            "tournament": {"uniqueTournament": {"name": "FIFA World Cup"}},
            "roundInfo": {"name": "Quarterfinals"},
            "venue": {
                "name": "Test Stadium",
                "city": {"name": "Dallas"},
                "country": {"name": "USA"},
            },
        }
    }
    monkeypatch.setattr(
        "world_cup_intelligence.inference.fetch_sofascore_event",
        lambda _event_id: payload,
    )
    service = object.__new__(PredictionService)
    service.source_team_ids = {
        4752: SimpleNamespace(
            team_id="canada", team_name="Canada", country_name="Canada"
        ),
        4781: SimpleNamespace(
            team_id="mexico", team_name="Mexico", country_name="Mexico"
        ),
    }
    monkeypatch.setattr(
        service,
        "predict_match",
        lambda home_team_id, away_team_id, context=None: {
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_win": 0.4,
            "draw": 0.3,
            "away_win": 0.3,
            "prematch_context": context,
        },
    )
    prediction = service.predict_sofascore_link(
        "https://www.sofascore.com/football/match/canada-mexico/x#id:99999999"
    )
    context = prediction["prematch_context"]
    assert prediction["home_team_id"] == "canada"
    assert prediction["away_team_id"] == "mexico"
    assert context["round_name"] == "Quarterfinals"
    assert context["venue_name"] == "Test Stadium"
    assert context["neutral_site"] == 1
    assert prediction["home_win"] + prediction["draw"] + prediction[
        "away_win"
    ] == pytest.approx(1)
