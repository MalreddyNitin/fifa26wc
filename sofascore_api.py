import json
import time
from pathlib import Path

from curl_cffi import requests


BASE_URL = "https://www.sofascore.com/api/v1"
CACHE_DIR = Path(__file__).resolve().parent / ".sofascore_cache"
MIN_REQUEST_INTERVAL = 0.15

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.sofascore.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/149.0.0.0 Safari/537.36",
}

_SESSION = requests.Session()
_LAST_REQUEST_AT = 0.0


def fetch_json(path, cache_group=None, cache_key=None, required_key=None, retries=3):
    """Fetch a SofaScore JSON object, reusing a successful cached response."""
    global _LAST_REQUEST_AT

    cache_path = None

    if cache_group is not None and cache_key is not None:
        cache_path = CACHE_DIR / cache_group / f"{cache_key}.json"

        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # Ignore an incomplete cache file and replace it after a
                # successful request.
                pass

    url = f"{BASE_URL}/{path.lstrip('/')}"

    for attempt in range(retries):
        elapsed = time.monotonic() - _LAST_REQUEST_AT
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        try:
            response = _SESSION.get(
                url,
                headers=HEADERS,
                impersonate="chrome",
                timeout=30,
            )
            _LAST_REQUEST_AT = time.monotonic()
        except requests.RequestsError as exc:
            _LAST_REQUEST_AT = time.monotonic()
            if attempt == retries - 1:
                print(f"Request failed for {url}: {exc}")
                return None
            time.sleep(2 ** attempt)
            continue

        if response.status_code == 200:
            try:
                data = response.json()
            except (ValueError, json.JSONDecodeError):
                print(f"Invalid JSON for {url}")
                return None

            if required_key is not None and required_key not in data:
                return data

            if cache_path is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(
                        json.dumps(data, separators=(",", ":")),
                        encoding="utf-8",
                    )
                except OSError as exc:
                    print(f"Could not cache {url}: {exc}")

            return data

        if response.status_code == 404:
            return None

        if response.status_code not in {429, 500, 502, 503, 504}:
            print(f"Request failed for {url}: HTTP {response.status_code}")
            return None

        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    print(f"Request failed for {url}: HTTP {response.status_code}")
    return None
