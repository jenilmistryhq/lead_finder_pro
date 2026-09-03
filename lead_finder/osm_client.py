"""Free-forever business search using OpenStreetMap — no API key, no
billing account, no card on file, no monthly limit, ever.

Uses two public OSM services:
  - Nominatim: geocodes a city name to a bounding box
  - Overpass:  queries tagged points-of-interest inside that box

Trade-off vs the Google provider: OSM's business data is crowdsourced.
Website/phone are missing far more often than on a claimed Google
Business Profile, and OSM stores NO rating/review data at all — that
signal comes back as None (not zero) for every lead, meaning the
"gap" here really just means: no website, or no phone listed at all.
Coverage also varies a lot by region — dense in many major cities,
thin in others.

Be a good citizen of shared, volunteer-run infrastructure:
  - Nominatim usage policy (~1 request/sec, real User-Agent required):
    https://operations.osmfoundation.org/policies/nominatim/
  - Overpass fair-use guidance:
    https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from .exceptions import PlacesAPIError

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "lead-finder/1.0 (personal lead-research script; contact: set your own)"

# Common niche -> OSM tag mapping. Not exhaustive — pass --osm-tag
# "key=value" directly for anything not listed. Browse tags at
# https://wiki.openstreetmap.org/wiki/Map_features
NICHE_TAG_MAP = {
    "dentist": "amenity=dentist",
    "doctor": "amenity=doctors",
    "clinic": "amenity=clinic",
    "chiropractor": "healthcare=chiropractor",
    "physiotherapist": "healthcare=physiotherapist",
    "physical therapist": "healthcare=physiotherapist",
    "lawyer": "office=lawyer",
    "law firm": "office=lawyer",
    "attorney": "office=lawyer",
    "real estate agent": "office=estate_agent",
    "real estate": "office=estate_agent",
    "roofer": "craft=roofer",
    "roofing": "craft=roofer",
    "plumber": "craft=plumber",
    "electrician": "craft=electrician",
    "hvac": "craft=hvac",
    "hair salon": "shop=hairdresser",
    "salon": "shop=hairdresser",
    "gym": "leisure=fitness_centre",
    "fitness center": "leisure=fitness_centre",
    "restaurant": "amenity=restaurant",
    "cafe": "amenity=cafe",
    "coffee shop": "amenity=cafe",
    "auto repair": "shop=car_repair",
    "mechanic": "shop=car_repair",
    "veterinarian": "amenity=veterinary",
    "vet": "amenity=veterinary",
    "bakery": "shop=bakery",
    "accountant": "office=accountant",
}


class OverpassClient:
    def __init__(
        self,
        max_retries: int = 3,
        timeout: float = 30.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _geocode_city(self, city: str) -> dict:
        params = {"q": city, "format": "json", "limit": 1}
        resp = self.session.get(NOMINATIM_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise PlacesAPIError(f"Could not geocode city: {city!r}")
        south, north, west, east = results[0]["boundingbox"]
        return {"south": south, "north": north, "west": west, "east": east}

    def _resolve_tag(self, niche: str, osm_tag: Optional[str]) -> str:
        if osm_tag:
            return osm_tag
        key = niche.strip().lower()
        if key in NICHE_TAG_MAP:
            return NICHE_TAG_MAP[key]
        raise PlacesAPIError(
            f"No built-in OSM tag for niche {niche!r}. Pass --osm-tag "
            f'"key=value" (e.g. --osm-tag "shop=bakery") — browse tags at '
            f"https://wiki.openstreetmap.org/wiki/Map_features"
        )

    def text_search(
        self, niche: str, city: str, max_results: int, osm_tag: Optional[str] = None
    ) -> list:
        tag = self._resolve_tag(niche, osm_tag)
        tag_key, tag_value = tag.split("=", 1)

        bbox = self._geocode_city(city)
        time.sleep(1)  # respect Nominatim's ~1 request/sec policy

        query = (
            f"[out:json][timeout:{int(self.timeout)}];"
            f'(node["{tag_key}"="{tag_value}"]'
            f"({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});"
            f'way["{tag_key}"="{tag_value}"]'
            f"({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});"
            f");out center tags {max_results};"
        )

        last_error: Optional[Exception] = None
        data = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(
                    OVERPASS_URL, data={"data": query}, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as exc:
                last_error = exc
                wait = min(2**attempt, 20)
                logger.warning(
                    "Overpass request failed (attempt %d/%d): %s — retrying in %ds",
                    attempt, self.max_retries, exc, wait,
                )
                time.sleep(wait)

        if data is None:
            raise PlacesAPIError(
                f"Overpass request failed after {self.max_retries} attempts: {last_error}"
            )

        elements = data.get("elements", [])[:max_results]
        logger.info(
            "Overpass returned %d elements for %s (%s in %s)",
            len(elements), tag, niche, city,
        )
        return [_normalize(el) for el in elements]


def _normalize(element: dict) -> dict:
    tags = element.get("tags", {})
    website = tags.get("website") or tags.get("contact:website")
    phone = tags.get("phone") or tags.get("contact:phone")
    address_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:city", ""),
    ]
    address = " ".join(p for p in address_parts if p)
    types = [
        tags.get(k, "")
        for k in ("amenity", "shop", "craft", "office", "healthcare", "leisure")
        if k in tags
    ]

    return {
        "place_id": f"osm:{element.get('type')}:{element.get('id')}",
        "name": tags.get("name", ""),
        "formatted_phone_number": phone or "",
        "website": website,
        "rating": None,  # OSM has no review/rating data — genuinely unknown
        "user_ratings_total": None,
        "business_status": "OPERATIONAL",  # OSM doesn't track operational status
        "formatted_address": address,
        "types": types,
    }
