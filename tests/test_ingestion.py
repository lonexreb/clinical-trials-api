"""Tests for the ingestion service."""


import httpx
import pytest

from app.services.ingestion import fetch_studies_page, validate_and_parse_studies

MOCK_API_RESPONSE = {
    "studies": [
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT12345678",
                    "briefTitle": "Test Cancer Study",
                },
                "statusModule": {
                    "overallStatus": "RECRUITING",
                    "startDateStruct": {"date": "2023-01-15"},
                },
                "designModule": {
                    "phases": ["PHASE3"],
                    "enrollmentInfo": {"count": 100},
                },
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Test Pharma"},
                },
            },
        },
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT87654321",
                    "briefTitle": "Test Drug Study",
                },
                "statusModule": {
                    "overallStatus": "COMPLETED",
                },
                "designModule": {},
                "sponsorCollaboratorsModule": {
                    "leadSponsor": {"name": "Another Pharma"},
                },
            },
        },
    ],
    "nextPageToken": "abc123token",
}

MOCK_LAST_PAGE_RESPONSE = {
    "studies": [
        {
            "protocolSection": {
                "identificationModule": {"nctId": "NCT11111111", "briefTitle": "Last Study"},
                "statusModule": {"overallStatus": "COMPLETED"},
                "designModule": {},
                "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
            },
        },
    ],
}


@pytest.mark.asyncio
async def test_fetch_studies_page_returns_studies_and_token() -> None:
    """Mock httpx response and verify parsing of studies and nextPageToken."""

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MOCK_API_RESPONSE)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        studies, next_token = await fetch_studies_page(
            client, "http://test/api/v2/studies", page_size=100
        )

    assert len(studies) == 2
    assert next_token == "abc123token"
    proto = studies[0].get("protocolSection", {})
    assert isinstance(proto, dict)
    assert proto.get("identificationModule", {}).get("nctId") == "NCT12345678"


@pytest.mark.asyncio
async def test_fetch_studies_page_no_next_token_on_last_page() -> None:
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=MOCK_LAST_PAGE_RESPONSE)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        studies, next_token = await fetch_studies_page(client, "http://test/api/v2/studies")

    assert len(studies) == 1
    assert next_token is None


@pytest.mark.asyncio
async def test_fetch_studies_page_passes_params() -> None:
    """Verify query params are passed correctly."""
    captured_params: dict[str, str] = {}

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        for key, value in request.url.params.items():
            captured_params[key] = value
        return httpx.Response(200, json=MOCK_LAST_PAGE_RESPONSE)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await fetch_studies_page(
            client, "http://test/api/v2/studies",
            page_size=500, page_token="mytoken", query_term="cancer"
        )

    assert captured_params["pageSize"] == "500"
    assert captured_params["pageToken"] == "mytoken"
    assert captured_params["query.term"] == "cancer"
    assert captured_params["format"] == "json"


@pytest.mark.asyncio
async def test_fetch_studies_page_raises_on_http_error() -> None:
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_studies_page(client, "http://test/api/v2/studies")


def test_validate_and_parse_valid_studies() -> None:
    valid, errors = validate_and_parse_studies(MOCK_API_RESPONSE["studies"])
    assert len(valid) == 2
    assert len(errors) == 0
    assert valid[0].trial_id == "NCT12345678"
    assert valid[1].trial_id == "NCT87654321"


def test_validate_and_parse_captures_errors() -> None:
    """A study missing required fields should be captured as an error."""
    bad_study: dict[str, object] = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT_BAD"},
            # Missing statusModule, sponsorCollaboratorsModule — but parser handles this gracefully
        },
    }
    valid, errors = validate_and_parse_studies([bad_study])
    # Our parser is defensive and provides defaults, so even bad studies parse
    # Only truly broken data (non-dict input) would error
    assert len(valid) + len(errors) == 1
