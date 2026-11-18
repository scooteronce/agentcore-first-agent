import json
from unittest.mock import MagicMock, patch

from main import check_aws_health

# A couple of mock events from different regions
US_EAST_1_EVENT = {
    "arn": "arn:aws:health:us-east-1::event/S3/AWS_S3_OPERATIONAL_ISSUE/AWS_S3_OPERATIONAL_ISSUE_ABC",
    "service": "s3-us-east-1",
    "service_name": "Amazon S3",
    "region_name": "N. Virginia",
    "summary": "Increased error rates for S3 requests",
    "event_log": [
        {"timestamp": 100, "message": "Investigating"},
        {"timestamp": 200, "message": "Recovery in progress"},
    ],
}

ME_CENTRAL_1_EVENT = {
    "arn": "arn:aws:health:me-central-1::event/MULTIPLE_SERVICES/AWS_MULTIPLE_SERVICES_OPERATIONAL_ISSUE/X",
    "service": "multipleservices-me-central-1",
    "service_name": "Multiple services",
    "region_name": "UAE",
    "summary": "Connectivity issues",
    "event_log": [],
}


def mock_feed(events):
    """Patch urllib so the health feed returns the given events, UTF-16 encoded like the real feed."""
    response = MagicMock()
    response.read.return_value = json.dumps(events).encode("utf-16")
    cm = MagicMock()
    cm.__enter__.return_value = response
    return patch("urllib.request.urlopen", return_value=cm)


def test_no_incidents():
    with mock_feed([]):
        result = check_aws_health()
    assert "No ongoing AWS incidents across all regions" in result


def test_no_incidents_in_requested_region():
    with mock_feed([US_EAST_1_EVENT]):
        result = check_aws_health(region="eu-west-1")
    assert "No ongoing AWS incidents in eu-west-1" in result


def test_reports_incident_with_latest_update():
    with mock_feed([US_EAST_1_EVENT]):
        result = check_aws_health()
    assert "1 ongoing AWS incident(s)" in result
    assert "Amazon S3" in result
    assert "N. Virginia" in result
    assert "Increased error rates" in result
    # The most recent event_log entry wins, not the first.
    assert "Recovery in progress" in result
    assert "Investigating" not in result


def test_region_filter_matches_region_code_in_arn_and_service():
    with mock_feed([US_EAST_1_EVENT, ME_CENTRAL_1_EVENT]):
        result = check_aws_health(region="me-central-1")
    assert "1 ongoing AWS incident(s)" in result
    assert "Multiple services" in result
    assert "Amazon S3" not in result


def test_region_filter_is_case_insensitive():
    with mock_feed([US_EAST_1_EVENT]):
        result = check_aws_health(region="US-EAST-1")
    assert "Amazon S3" in result


def test_fetch_failure_returns_message_instead_of_raising():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        result = check_aws_health()
    assert "Could not reach the AWS Health feed" in result
    assert "connection refused" in result


def test_event_with_empty_event_log_reports_no_update():
    with mock_feed([ME_CENTRAL_1_EVENT]):
        result = check_aws_health()
    assert "Latest update: none" in result
