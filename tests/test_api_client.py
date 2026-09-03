from unittest.mock import MagicMock, patch

import pytest

from lead_finder.api_client import PlacesClient
from lead_finder.exceptions import PlacesAPIError


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_basic_search_returns_normalized_places(mock_post, _sleep):
    mock_post.return_value = _mock_response({
        "places": [{
            "id": "p1",
            "displayName": {"text": "Bright Smile Dental"},
            "formattedAddress": "1 Main St",
            "nationalPhoneNumber": "555-0000",
            "websiteUri": None,
            "businessStatus": "OPERATIONAL",
            "types": ["dentist"],
        }],
    })
    client = PlacesClient(api_key="fake", max_retries=3)
    results = client.text_search("dentist in Austin", max_results=10)
    assert len(results) == 1
    assert results[0]["name"] == "Bright Smile Dental"
    assert results[0]["place_id"] == "p1"
    assert results[0]["website"] is None


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_default_field_mask_excludes_rating(mock_post, _sleep):
    mock_post.return_value = _mock_response({"places": []})
    client = PlacesClient(api_key="fake", max_retries=3, include_ratings=False)
    client.text_search("dentist in Austin", max_results=10)
    headers = mock_post.call_args.kwargs["headers"]
    assert "places.rating" not in headers["X-Goog-FieldMask"]


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_include_ratings_adds_rating_fields(mock_post, _sleep):
    mock_post.return_value = _mock_response({"places": []})
    client = PlacesClient(api_key="fake", max_retries=3, include_ratings=True)
    client.text_search("dentist in Austin", max_results=10)
    headers = mock_post.call_args.kwargs["headers"]
    assert "places.rating" in headers["X-Goog-FieldMask"]
    assert "places.userRatingCount" in headers["X-Goog-FieldMask"]


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_retries_on_retryable_http_status_then_succeeds(mock_post, _sleep):
    mock_post.side_effect = [
        _mock_response({"error": "rate limited"}, status_code=429),
        _mock_response({"places": [{"id": "1", "displayName": {"text": "X"}}]}, status_code=200),
    ]
    client = PlacesClient(api_key="fake", max_retries=3)
    results = client.text_search("dentist in Austin", max_results=10)
    assert len(results) == 1
    assert mock_post.call_count == 2


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_raises_on_non_retryable_http_status(mock_post, _sleep):
    mock_post.return_value = _mock_response({"error": "bad key"}, status_code=403)
    client = PlacesClient(api_key="fake", max_retries=3)
    with pytest.raises(PlacesAPIError):
        client.text_search("dentist in Austin", max_results=10)


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_pagination_stops_without_next_page_token(mock_post, _sleep):
    mock_post.return_value = _mock_response(
        {"places": [{"id": "1", "displayName": {"text": "X"}}]}
    )
    client = PlacesClient(api_key="fake", max_retries=3)
    results = client.text_search("dentist in Austin", max_results=10)
    assert len(results) == 1
    assert mock_post.call_count == 1


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_respects_max_results_across_pages(mock_post, _sleep):
    mock_post.side_effect = [
        _mock_response({
            "places": [{"id": str(i), "displayName": {"text": f"biz{i}"}} for i in range(20)],
            "nextPageToken": "tok1",
        }),
        _mock_response({
            "places": [{"id": str(i), "displayName": {"text": f"biz{i}"}} for i in range(20, 40)],
        }),
    ]
    client = PlacesClient(api_key="fake", max_retries=3)
    results = client.text_search("dentist in Austin", max_results=25)
    assert len(results) == 25


@patch("time.sleep", return_value=None)
@patch("requests.Session.post")
def test_exhausts_retries_and_raises(mock_post, _sleep):
    mock_post.return_value = _mock_response({"error": "unavailable"}, status_code=503)
    client = PlacesClient(api_key="fake", max_retries=2)
    with pytest.raises(PlacesAPIError):
        client.text_search("dentist in Austin", max_results=10)
    assert mock_post.call_count == 2
