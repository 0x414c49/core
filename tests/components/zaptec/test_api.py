"""Test the Zaptec API client."""

from unittest.mock import patch

import pytest

from homeassistant.components.zaptec.api import (
    ZaptecApiError,
    ZaptecClient,
    ZaptecConnectionError,
)
from homeassistant.components.zaptec.const import API_URL, TOKEN_URL, TOKEN_URL_LEGACY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PASSWORD, USERNAME

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


async def test_token_retries_transient_503(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test token requests retry transient 503 responses."""

    async def token_response(
        method: str, url: str, data: object
    ) -> AiohttpClientMockResponse:
        if len(aioclient_mock.mock_calls) == 1:
            return AiohttpClientMockResponse(method, url, status=503)
        return AiohttpClientMockResponse(
            method, url, json={"access_token": "test-access-token"}
        )

    aioclient_mock.post(TOKEN_URL, side_effect=token_response)
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with patch("homeassistant.components.zaptec.api.asyncio.sleep") as sleep_mock:
        token = await client.async_get_access_token()

    assert token == "test-access-token"
    sleep_mock.assert_called_once()
    assert len(aioclient_mock.mock_calls) == 2


async def test_token_falls_back_to_legacy_endpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test token requests fall back when the primary endpoint rejects credentials."""
    aioclient_mock.post(
        TOKEN_URL,
        status=400,
        json={"error_description": "Primary rejected credentials"},
    )
    aioclient_mock.post(TOKEN_URL_LEGACY, json={"access_token": "legacy-token"})
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with patch("homeassistant.components.zaptec.api.asyncio.sleep"):
        token = await client.async_get_access_token()

    assert token == "legacy-token"
    assert len(aioclient_mock.mock_calls) == 2


async def test_token_non_dict_json_falls_back_to_legacy_endpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test non-object token responses do not raise unexpected errors."""
    aioclient_mock.post(TOKEN_URL, json=[])
    aioclient_mock.post(TOKEN_URL_LEGACY, json={"access_token": "legacy-token"})
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    token = await client.async_get_access_token()

    assert token == "legacy-token"


async def test_token_is_reused_for_api_requests(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a successful token request is cached."""
    aioclient_mock.post(TOKEN_URL, json={"access_token": "test-access-token"})
    aioclient_mock.get(f"{API_URL}installation", json={"Data": []})
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    token = await client.async_get_access_token()
    data = await client.async_get("installation")

    assert token == "test-access-token"
    assert data == {"data": []}
    assert len(aioclient_mock.mock_calls) == 2


async def test_token_persistent_503_raises_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test persistent token 503 responses are treated as connection errors."""
    aioclient_mock.post(TOKEN_URL, status=503)
    aioclient_mock.post(TOKEN_URL_LEGACY, status=503)
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with (
        patch("homeassistant.components.zaptec.api.asyncio.sleep"),
        pytest.raises(ZaptecConnectionError),
    ):
        await client.async_get_access_token()

    assert len(aioclient_mock.mock_calls) == 10


async def test_token_persistent_500_raises_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test persistent token 500 responses are treated as connection errors."""
    aioclient_mock.post(TOKEN_URL, status=500)
    aioclient_mock.post(TOKEN_URL_LEGACY, status=500)
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with (
        patch("homeassistant.components.zaptec.api.asyncio.sleep"),
        pytest.raises(ZaptecConnectionError),
    ):
        await client.async_get_access_token()

    assert len(aioclient_mock.mock_calls) == 10


async def test_api_persistent_503_raises_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test persistent API 503 responses are treated as connection errors."""
    aioclient_mock.get(f"{API_URL}installation", status=503)
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with (
        patch("homeassistant.components.zaptec.api.asyncio.sleep"),
        pytest.raises(ZaptecConnectionError),
    ):
        await client.async_request("GET", "installation", authenticated=False)

    assert len(aioclient_mock.mock_calls) == 5


async def test_api_retries_transient_500(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test API requests retry transient 500 responses."""

    async def response(
        method: str, url: str, data: object
    ) -> AiohttpClientMockResponse:
        if len(aioclient_mock.mock_calls) == 1:
            return AiohttpClientMockResponse(method, url, status=500)
        return AiohttpClientMockResponse(method, url, json={"Data": []})

    aioclient_mock.get(f"{API_URL}installation", side_effect=response)
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with patch("homeassistant.components.zaptec.api.asyncio.sleep") as sleep_mock:
        data = await client.async_request("GET", "installation", authenticated=False)

    assert data == {"data": []}
    sleep_mock.assert_called_once()
    assert len(aioclient_mock.mock_calls) == 2


async def test_api_invalid_json_raises_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test invalid success responses raise an integration error."""
    aioclient_mock.get(f"{API_URL}installation", text="not json")
    client = ZaptecClient(async_get_clientsession(hass), USERNAME, PASSWORD)

    with pytest.raises(ZaptecApiError):
        await client.async_request("GET", "installation", authenticated=False)
