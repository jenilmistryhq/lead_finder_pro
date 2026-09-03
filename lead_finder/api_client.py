"""Retrying wrapper around Google's Places API (New).

Deliberately targets the CURRENT API — the older "Places API (Legacy)"
endpoints (maps.googleapis.com/maps/api/place/...) can no longer be
enabled on new Google Cloud projects at all (Google froze Legacy to new
projects in March 2025). A script built against Legacy fails outright
with REQUEST_DENIED for anyone setting this up fresh in 2026.

Docs: https://developers.google.com/maps/documentation/places/web-service/text-search

Cost note: Text Search (New) bills at Pro-tier pricing by default (5,000
free calls/month). Adding rating/review fields to the field mask bumps
the ENTIRE call to Enterprise-tier pricing (only 1,000 free calls/month,
~$35-40/1,000 after that) — Google bills every field in a response at the
highest tier any single requested field belongs to. This client leaves
rating/review fields OUT of the default field mask for that reason; pass
include_ratings=True if you specifically want them and accept the cost.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from .exceptions import PlacesAPIError

logger = logging.getLogger(__name__)

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"

BASE_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri,places.businessStatus,"
    "places.types,nextPageToken"
)
RATING_FIELDS = "places.rating,places.userRatingCount"

RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class PlacesClient:
    """Text Search (New) already returns phone/website/type data in one
    call — no separate per-place Details request needed, unlike the old
    Legacy flow (search, then N detail calls). That means the billable
    unit here is roughly one call per ~20 results, not one per business."""

    def __init__(
        self,
        api_key: str,
        max_retries: int = 4,
        timeout: float = 15.0,
        include_ratings: bool = False,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.include_ratings = include_ratings
        self.session = session or requests.Session()
        if include_ratings:
            logger.warning(
                "include_ratings=True: this call now bills at Enterprise-tier "
                "pricing (only 1,000 free calls/month) instead of Pro-tier "
                "(5,000 free calls/month)."
            )

    @property
    def _field_mask(self) -> str:
        return BASE_FIELDS + ("," + RATING_FIELDS if self.include_ratings else "")

    def _post(self, body: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": self._field_mask,
        }
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    SEARCH_TEXT_URL, json=body, headers=headers, timeout=self.timeout
                )
            except requests.RequestException as exc:
                last_error = exc
                wait = min(2**attempt, 30)
                logger.warning(
                    "Request failed (attempt %d/%d): %s — retrying in %ds",
                    attempt, self.max_retries, exc, wait,
                )
                time.sleep(wait)
                continue

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in RETRYABLE_HTTP_STATUSES and attempt < self.max_retries:
                wait = min(2**attempt, 30)
                logger.warning(
                    "HTTP %d from Places API — retrying in %ds (attempt %d/%d)",
                    resp.status_code, wait, attempt, self.max_retries,
                )
                time.sleep(wait)
                continue

            raise PlacesAPIError(
                f"Places API error: HTTP {resp.status_code} — {resp.text[:300]}"
            )

        raise PlacesAPIError(
            f"Request failed after {self.max_retries} attempts: {last_error}"
        )

    def text_search(self, query: str, max_results: int) -> list:
        """Paginate Text Search (New) up to max_results."""
        results: list = []
        body = {"textQuery": query}
        page = 1

        while True:
            data = self._post(body)
            batch = data.get("places", [])
            results.extend(batch)
            logger.info(
                "Page %d: +%d results (total %d)", page, len(batch), len(results)
            )

            token = data.get("nextPageToken")
            if not token or len(results) >= max_results:
                break

            time.sleep(2)  # short delay before a new pageToken becomes valid
            body = {"textQuery": query, "pageToken": token}
            page += 1

        return [_normalize(p) for p in results[:max_results]]


def _normalize(place: dict) -> dict:
    """Map Places API (New) field names onto the provider-neutral shape
    scoring.py expects (same shape the OSM provider normalizes to)."""
    return {
        "place_id": place.get("id", ""),
        "name": (place.get("displayName") or {}).get("text", ""),
        "formatted_phone_number": place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri"),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("userRatingCount"),
        "business_status": place.get("businessStatus", "OPERATIONAL"),
        "formatted_address": place.get("formattedAddress", ""),
        "types": place.get("types", []),
    }
