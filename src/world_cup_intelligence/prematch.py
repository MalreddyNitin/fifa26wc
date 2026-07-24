import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from curl_cffi import requests

from .canonical import classify_competition
from .pipeline import normalize_country_name, safe_nested, timestamp_to_datetime

SOFASCORE_HOSTS = {"sofascore.com", "www.sofascore.com"}
SOFASCORE_EVENT_BASE_URLS = (
    "https://api.sofascore.com/api/v1",
    "https://www.sofascore.com/api/v1",
)


class PrematchLookupError(ValueError):
    """A SofaScore URL or event payload cannot produce a model fixture."""


@dataclass(frozen=True)
class PrematchEvent:
    event_id: int
    kickoff_utc: object
    home_sofascore_team_id: int
    away_sofascore_team_id: int
    home_team_name: str
    away_team_name: str
    tournament_name: str | None
    competition_type: str
    round_name: str
    venue_name: str | None
    venue_city: str | None
    venue_country: str | None
    neutral_site: int | None
    home_displayed_ranking: float | None
    away_displayed_ranking: float | None

    def as_dict(self):
        kickoff = self.kickoff_utc
        return {
            **self.__dict__,
            "kickoff_utc": kickoff.isoformat()
            if hasattr(kickoff, "isoformat")
            else None,
        }


def parse_sofascore_event_id(value):
    """Extract the numeric event ID from a public SofaScore match URL."""
    text = str(value or "").strip()
    try:
        parsed = urlparse(text)
    except ValueError as exc:
        raise PrematchLookupError("Invalid SofaScore match URL") from exc
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"} or hostname not in SOFASCORE_HOSTS:
        raise PrematchLookupError("Use a https://www.sofascore.com match link")

    query = parse_qs(parsed.query)
    for key in ("id", "eventId", "event_id"):
        for candidate in query.get(key, []):
            if str(candidate).isdigit():
                return int(candidate)

    for source, pattern in (
        (parsed.fragment, r"(?:^|[&])id:(\d+)(?:$|[&])"),
        (parsed.fragment, r"(?:^|[&])id=(\d+)(?:$|[&])"),
        (parsed.path, r"/event/(\d+)(?:/|$)"),
    ):
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    raise PrematchLookupError(
        "The link does not contain a SofaScore event ID (normally #id:12345678)"
    )


def _optional_number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def event_from_payload(event_id, payload, home_country=None, away_country=None):
    event = payload.get("event", payload)
    home_source_id = safe_nested(event, "homeTeam", "id")
    away_source_id = safe_nested(event, "awayTeam", "id")
    if home_source_id is None or away_source_id is None:
        raise PrematchLookupError("SofaScore event does not contain two teams")

    tournament_name = safe_nested(event, "tournament", "uniqueTournament", "name")
    tournament_name = tournament_name or safe_nested(event, "tournament", "name")
    round_name = safe_nested(event, "roundInfo", "name")
    if not round_name:
        round_number = safe_nested(event, "roundInfo", "round")
        round_name = f"Round {round_number}" if round_number is not None else "fixture"

    venue_country = safe_nested(event, "venue", "country", "name")
    explicit_neutral = event.get("neutralGround")
    if isinstance(explicit_neutral, bool):
        neutral_site = int(explicit_neutral)
    elif venue_country and home_country and away_country:
        venue = normalize_country_name(venue_country)
        neutral_site = int(
            venue != normalize_country_name(home_country)
            and venue != normalize_country_name(away_country)
        )
    else:
        neutral_site = None

    return PrematchEvent(
        event_id=int(event_id),
        kickoff_utc=timestamp_to_datetime(event.get("startTimestamp")),
        home_sofascore_team_id=int(home_source_id),
        away_sofascore_team_id=int(away_source_id),
        home_team_name=safe_nested(event, "homeTeam", "name") or str(home_source_id),
        away_team_name=safe_nested(event, "awayTeam", "name") or str(away_source_id),
        tournament_name=tournament_name,
        competition_type=classify_competition(tournament_name),
        round_name=str(round_name),
        venue_name=safe_nested(event, "venue", "name"),
        venue_city=safe_nested(event, "venue", "city", "name"),
        venue_country=venue_country,
        neutral_site=neutral_site,
        home_displayed_ranking=_optional_number(
            safe_nested(event, "homeTeam", "ranking")
        ),
        away_displayed_ranking=_optional_number(
            safe_nested(event, "awayTeam", "ranking")
        ),
    )


def fetch_sofascore_event(event_id, retries=3, timeout=20):
    """Fetch only public event metadata; no in-match statistics are requested."""
    headers = {
        "accept": "application/json",
        "referer": "https://www.sofascore.com/",
        "x-requested-with": "XMLHttpRequest",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/149 Safari/537.36"
        ),
    }
    response = None
    for attempt in range(retries):
        last_error = None
        retryable = False
        for base_url in SOFASCORE_EVENT_BASE_URLS:
            url = f"{base_url}/event/{int(event_id)}"
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    impersonate="chrome",
                    timeout=timeout,
                )
            except requests.RequestsError as exc:
                last_error = exc
                retryable = True
                continue
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise PrematchLookupError(
                        "SofaScore returned invalid JSON"
                    ) from exc
            if response.status_code == 404:
                raise PrematchLookupError(f"SofaScore event {event_id} was not found")
            if response.status_code in {401, 403}:
                continue
            if response.status_code in {429, 500, 502, 503, 504}:
                retryable = True
                continue
            raise PrematchLookupError(
                f"SofaScore event request failed with HTTP {response.status_code}"
            )
        if not retryable:
            status = response.status_code if response is not None else "unknown"
            raise PrematchLookupError(
                f"SofaScore event request failed with HTTP {status}"
            )
        if attempt == retries - 1 and last_error is not None and response is None:
            raise PrematchLookupError(
                f"Could not reach SofaScore: {last_error}"
            ) from last_error
        if attempt < retries - 1:
            time.sleep(2**attempt)
    status = response.status_code if response is not None else "unknown"
    raise PrematchLookupError(f"SofaScore event request failed with HTTP {status}")


def fetched_at_utc():
    return datetime.now(timezone.utc).isoformat()
