"""The Lead record and the gap-based scoring model.

Scoring mirrors the manual checklist from the lead-finding masterclass:
no website, thin review count, below-average rating, and a non-operational
business status are all scored as gaps worth an outreach angle.

Rating/review count can be genuinely UNAVAILABLE (not zero) — the OSM
provider has no review data at all, and Google's own response omits the
field for places with no ratings yet. Those cases are treated as "unknown,
skip this check" rather than silently scored as "0 reviews", which would
misrepresent missing data as a bad signal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar, Optional, Tuple


@dataclass
class Lead:
    place_id: str = ""
    name: str = ""
    phone: str = ""
    website: str = "NONE"
    category: str = ""
    rating: Optional[float] = None
    reviews: Optional[int] = None
    address: str = ""
    business_status: str = ""
    score: int = 0
    gap_notes: str = ""
    gbp_claimed: str = "CHECK MANUALLY"
    running_ads: str = "CHECK MANUALLY"
    status: str = "New"

    # Column order for exports — keeps CSV/XLSX/JSON consistent and stable
    # even if dataclass field order ever changes.
    FIELD_ORDER: ClassVar[tuple] = (
        "name", "phone", "website", "category", "rating", "reviews",
        "address", "business_status", "score", "gap_notes",
        "gbp_claimed", "running_ads", "status", "place_id",
    )

    def as_row(self) -> dict:
        d = asdict(self)
        return {k: d[k] for k in self.FIELD_ORDER}


def score_details(details: dict, min_reviews_threshold: int) -> Tuple[int, str]:
    score = 0
    notes = []

    if not details.get("website"):
        score += 25
        notes.append("No website")

    reviews = details.get("user_ratings_total")
    if reviews is not None and reviews < min_reviews_threshold:
        score += 15
        notes.append(f"Weak review count ({reviews})")

    rating = details.get("rating")
    if rating is not None and rating < 4.0:
        score += 10
        notes.append(f"Below-average rating ({rating})")

    status = details.get("business_status", "OPERATIONAL")
    if status != "OPERATIONAL":
        score -= 50
        notes.append(f"Business status: {status} — verify it's still open")

    if reviews is None and rating is None:
        notes.append("No review/rating data from this source — check manually")

    return score, "; ".join(notes) if notes else "No obvious gap found"


def details_to_lead(place_id: str, details: dict, min_reviews_threshold: int) -> Lead:
    score, notes = score_details(details, min_reviews_threshold)
    return Lead(
        place_id=place_id,
        name=details.get("name", ""),
        phone=details.get("formatted_phone_number", ""),
        website=details.get("website") or "NONE",
        category=", ".join(t for t in details.get("types", []) if t)[:60],
        rating=details.get("rating"),
        reviews=details.get("user_ratings_total"),
        address=details.get("formatted_address", ""),
        business_status=details.get("business_status", ""),
        score=score,
        gap_notes=notes,
    )
