from unittest.mock import MagicMock, patch

import pytest

from lead_finder.exceptions import PlacesAPIError
from lead_finder.osm_client import NICHE_TAG_MAP, OverpassClient


def _mock_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
@patch("requests.Session.get")
def test_known_niche_resolves_and_returns_normalized_leads(mock_get, mock_post, _sleep):
    mock_get.return_value = _mock_response(
        [{"boundingbox": ["30.0", "30.5", "-97.9", "-97.5"]}]
    )
    mock_post.return_value = _mock_response({
        "elements": [{
            "type": "node",
            "id": 123,
            "tags": {
                "name": "Bright Smile Dental",
                "phone": "555-0000",
                "website": "https://brightsmile.example",
                "addr:housenumber": "1",
                "addr:street": "Main St",
                "addr:city": "Austin",
                "amenity": "dentist",
            },
        }]
    })
    client = OverpassClient(max_retries=3)
    results = client.text_search("dentist", "Austin, TX", max_results=10)

    assert len(results) == 1
    lead = results[0]
    assert lead["name"] == "Bright Smile Dental"
    assert lead["website"] == "https://brightsmile.example"
    assert lead["rating"] is None
    assert lead["user_ratings_total"] is None
    assert lead["place_id"] == "osm:node:123"


@patch("time.sleep", return_value=None)
@patch("requests.Session.get")
def test_unknown_niche_without_osm_tag_raises(mock_get, _sleep):
    mock_get.return_value = _mock_response(
        [{"boundingbox": ["30.0", "30.5", "-97.9", "-97.5"]}]
    )
    client = OverpassClient(max_retries=3)
    with pytest.raises(PlacesAPIError):
        client.text_search("underwater basket weaver", "Austin, TX", max_results=10)


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
@patch("requests.Session.get")
def test_explicit_osm_tag_overrides_niche_lookup(mock_get, mock_post, _sleep):
    mock_get.return_value = _mock_response(
        [{"boundingbox": ["30.0", "30.5", "-97.9", "-97.5"]}]
    )
    mock_post.return_value = _mock_response({"elements": []})
    client = OverpassClient(max_retries=3)
    client.text_search(
        "underwater basket weaver", "Austin, TX", max_results=10, osm_tag="shop=bakery"
    )
    sent_query = mock_post.call_args.kwargs["data"]["data"]
    assert 'shop"="bakery' in sent_query.replace(" ", "") or "shop" in sent_query


@patch("time.sleep", return_value=None)
@patch("requests.Session.get")
def test_geocode_failure_raises(mock_get, _sleep):
    mock_get.return_value = _mock_response([])  # no results
    client = OverpassClient(max_retries=3)
    with pytest.raises(PlacesAPIError):
        client.text_search("dentist", "Nowhereville", max_results=10)


def test_niche_tag_map_has_common_entries():
    assert "dentist" in NICHE_TAG_MAP
    assert "roofer" in NICHE_TAG_MAP
    assert "=" in NICHE_TAG_MAP["dentist"]
