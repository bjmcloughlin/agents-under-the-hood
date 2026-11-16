import os

import requests

# Overridable so you can point the server at a dead address and watch the failure path
BASE_URL = os.environ.get("OPENLIBRARY_URL", "https://openlibrary.org")
SEARCH_FIELDS = "key,title,author_name,first_publish_year,edition_count"


class OpenLibraryError(Exception):
    """Raised for a network failure or any non-2xx response. Carries the HTTP status."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def is_transient(self) -> bool:
        # No status means the request never got an answer: a timeout or a dropped connection
        return self.status_code is None or self.status_code == 429 or self.status_code >= 500

    @property
    def is_not_found(self) -> bool:
        return self.status_code == 404


class OpenLibraryClient:
    def __init__(self, user_agent: str, timeout: float = 10):
        self.timeout = timeout
        self.session = requests.Session()
        # Open Library asks clients to identify themselves
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise OpenLibraryError(f"Network error calling {url}: {e}") from e
        if not resp.ok:
            raise OpenLibraryError(f"{url} returned {resp.status_code}", resp.status_code)
        return resp.json()

    def search(self, query: str, limit: int) -> dict:
        return self._get("/search.json", {"q": query, "limit": limit, "fields": SEARCH_FIELDS})

    def work(self, work_id: str) -> dict:
        return self._get(f"/works/{work_id}.json")
