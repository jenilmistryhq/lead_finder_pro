from lead_finder.scoring import details_to_lead, score_details


def test_no_website_adds_points():
    score, notes = score_details(
        {"website": None, "user_ratings_total": 50, "rating": 4.5,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 25
    assert "No website" in notes


def test_weak_reviews_adds_points():
    score, notes = score_details(
        {"website": "https://x.com", "user_ratings_total": 3, "rating": 4.5,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 15
    assert "Weak review count" in notes


def test_low_rating_adds_points():
    score, notes = score_details(
        {"website": "https://x.com", "user_ratings_total": 50, "rating": 3.2,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 10
    assert "Below-average rating" in notes


def test_closed_business_penalized_below_zero():
    score, notes = score_details(
        {"website": "https://x.com", "user_ratings_total": 50, "rating": 4.8,
         "business_status": "CLOSED_PERMANENTLY"},
        min_reviews_threshold=10,
    )
    assert score < 0
    assert "Business status" in notes


def test_strong_business_scores_zero_with_no_gap_message():
    score, notes = score_details(
        {"website": "https://x.com", "user_ratings_total": 200, "rating": 4.9,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 0
    assert notes == "No obvious gap found"


def test_gaps_stack_additively():
    score, _ = score_details(
        {"website": None, "user_ratings_total": 1, "rating": 3.0,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 25 + 15 + 10  # all three gap conditions triggered


def test_missing_rating_and_reviews_are_skipped_not_penalized():
    """OSM-style data: no rating/review fields at all. Should NOT be
    treated as '0 reviews' or 'rating 0' — those checks should just
    be skipped, with a note that the data wasn't available."""
    score, notes = score_details(
        {"website": "https://x.com", "user_ratings_total": None, "rating": None,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 0
    assert "No review/rating data" in notes
    assert "Weak review count" not in notes
    assert "Below-average rating" not in notes


def test_missing_rating_with_no_website_still_flags_website_gap():
    score, notes = score_details(
        {"website": None, "user_ratings_total": None, "rating": None,
         "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert score == 25
    assert "No website" in notes
    assert "No review/rating data" in notes


def test_details_to_lead_maps_fields_and_defaults_missing_website():
    lead = details_to_lead(
        "abc123",
        {
            "name": "Test Biz",
            "formatted_phone_number": "555-0000",
            "website": None,
            "rating": 3.5,
            "user_ratings_total": 2,
            "business_status": "OPERATIONAL",
            "formatted_address": "1 St",
            "types": ["dentist", "health"],
        },
        min_reviews_threshold=10,
    )
    assert lead.place_id == "abc123"
    assert lead.name == "Test Biz"
    assert lead.website == "NONE"
    assert lead.category == "dentist, health"
    assert lead.score > 0


def test_details_to_lead_preserves_none_rating_reviews():
    lead = details_to_lead(
        "osm:node:1",
        {"name": "OSM Biz", "website": "https://x.com", "rating": None,
         "user_ratings_total": None, "business_status": "OPERATIONAL"},
        min_reviews_threshold=10,
    )
    assert lead.rating is None
    assert lead.reviews is None


def test_as_row_matches_field_order():
    lead = details_to_lead("id1", {"name": "X"}, min_reviews_threshold=10)
    row = lead.as_row()
    assert list(row.keys()) == list(lead.FIELD_ORDER)
