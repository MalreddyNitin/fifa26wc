import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests

from .storage import RawJsonStore

BASE_URL = "https://www.sofascore.com/api/v1"


@dataclass
class FetchResult:
    payload: dict
    status_code: int
    url: str
    payload_hash: str
    from_legacy_cache: bool = False


class SofaScoreClient:
    def __init__(
        self,
        raw_root,
        pipeline_run_id,
        request_interval=0.25,
        retries=4,
        timeout=30,
        legacy_cache_root=None,
    ):
        self.raw_store = RawJsonStore(raw_root)
        self.pipeline_run_id = pipeline_run_id
        self.request_interval = request_interval
        self.retries = retries
        self.timeout = timeout
        self.legacy_cache_root = Path(legacy_cache_root) if legacy_cache_root else None
        self._thread_local = threading.local()
        self._rate_lock = threading.Lock()
        self._next_request_at = 0.0
        self.headers = {
            "accept": "application/json",
            "referer": "https://www.sofascore.com/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/149 Safari/537.36"
            ),
        }

    def _session(self):
        if not hasattr(self._thread_local, "session"):
            self._thread_local.session = requests.Session()
        return self._thread_local.session

    def _wait_for_rate_limit(self):
        with self._rate_lock:
            now = time.monotonic()
            wait = max(0.0, self._next_request_at - now)
            if wait:
                time.sleep(wait)
            self._next_request_at = time.monotonic() + self.request_interval

    def _legacy_payload(self, cache_group, cache_key):
        if not self.legacy_cache_root or not cache_group or cache_key is None:
            return None
        path = self.legacy_cache_root / cache_group / f"{cache_key}.json"
        if not path.exists():
            return None
        import json

        return json.loads(path.read_text(encoding="utf-8"))

    def get_json(
        self,
        endpoint,
        category,
        partitions,
        legacy_cache_group=None,
        legacy_cache_key=None,
    ):
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        cached = self._legacy_payload(
            legacy_cache_group,
            legacy_cache_key,
        )
        if cached is not None:
            _, digest = self.raw_store.write(
                cached,
                category,
                partitions,
                url,
                endpoint,
                200,
                self.pipeline_run_id,
            )
            return FetchResult(cached, 200, url, digest, True)

        response = None
        for attempt in range(self.retries):
            self._wait_for_rate_limit()
            try:
                response = self._session().get(
                    url,
                    headers=self.headers,
                    impersonate="chrome",
                    timeout=self.timeout,
                )
            except requests.RequestsError:
                if attempt == self.retries - 1:
                    raise
                time.sleep(2**attempt)
                continue

            if response.status_code == 200:
                payload = response.json()
                _, digest = self.raw_store.write(
                    payload,
                    category,
                    partitions,
                    url,
                    endpoint,
                    response.status_code,
                    self.pipeline_run_id,
                )
                return FetchResult(
                    payload,
                    response.status_code,
                    url,
                    digest,
                )

            if response.status_code == 404:
                return None
            if response.status_code not in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            if attempt < self.retries - 1:
                time.sleep(2**attempt)

        if response is not None:
            response.raise_for_status()
        return None

    def search_team(self, query):
        return self.get_json(
            f"search/all?q={quote(query)}",
            "team_search",
            {"query": query.lower().replace(" ", "_")},
        )
