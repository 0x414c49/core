"""Async client for the Zaptec Cloud API.

Authentication uses the OAuth2 resource-owner password grant. The API returns
PascalCase JSON which is normalized to camelCase for downstream use.
"""

import asyncio
from contextlib import suppress
import logging
from typing import Any

import aiohttp

from .const import API_URL, TOKEN_URL, TOKEN_URL_LEGACY

_LOGGER = logging.getLogger(__name__)

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
RETRIES = 5
RETRY_INIT_DELAY = 0.5
RETRY_FACTOR = 1.8

TRUTHY = {"true", "1", "on", "yes"}
FALSY = {"false", "0", "off", "no"}


class ZaptecApiError(Exception):
    """Base error for Zaptec API failures."""


class ZaptecAuthError(ZaptecApiError):
    """Authentication failed (invalid credentials)."""


class ZaptecConnectionError(ZaptecApiError):
    """Could not communicate with the Zaptec API."""


def parse_bool(value: str | None) -> bool | None:
    """Parse a Zaptec boolean-ish observation value."""
    s = str(value if value is not None else "").strip().lower()
    if s in TRUTHY:
        return True
    if s in FALSY:
        return False
    return None


def parse_float(value: str | None) -> float | None:
    """Parse a Zaptec numeric observation value."""
    try:
        return float(str(value).strip())
    except TypeError, ValueError:
        return None


def _normalize(obj: Any) -> Any:
    """Recursively convert PascalCase dict keys to camelCase."""
    if isinstance(obj, dict):
        return {
            (k[:1].lower() + k[1:]) if k else k: _normalize(v) for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return obj


class ZaptecClient:
    """Minimal async client for the Zaptec Cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None

    async def async_get_access_token(self) -> str:
        """Authenticate and return an access token.

        Tries the primary token endpoint, falls back to the legacy endpoint
        (some accounts only authenticate there). Both retry on transient
        upstream 5xx responses, which the token service is known to emit.
        """
        auth_error: str = ""
        connection_error: str = ""
        for url in (TOKEN_URL, TOKEN_URL_LEGACY):
            endpoint_failed = False
            for attempt in range(1, RETRIES + 1):
                try:
                    async with self._session.post(
                        url,
                        data={
                            "grant_type": "password",
                            "username": self._username,
                            "password": self._password,
                        },
                        headers={"Accept": "application/json"},
                    ) as resp:
                        data: dict[str, Any] = {}
                        with suppress(aiohttp.ContentTypeError, ValueError):
                            parsed = await resp.json(content_type=None)
                            if isinstance(parsed, dict):
                                data = parsed
                        if resp.status < 300 and data.get("access_token"):
                            self._token = str(data["access_token"])
                            return self._token
                        if resp.status in (400, 401, 403):
                            # Credential rejection: try the other endpoint,
                            # but remember the message for the final error.
                            auth_error = str(
                                data.get("error_description")
                                or data.get("error")
                                or resp.status
                            )
                            _LOGGER.debug(
                                "Token endpoint %s rejected credentials: %s",
                                url,
                                auth_error,
                            )
                            break
                        if resp.status in RETRYABLE_STATUSES:
                            connection_error = (
                                f"Token endpoint {url} temporarily unavailable: "
                                f"{resp.status}"
                            )
                            if attempt < RETRIES:
                                delay = RETRY_INIT_DELAY * RETRY_FACTOR ** (attempt - 1)
                                _LOGGER.debug(
                                    "Token endpoint %s returned %s, retrying in %.1fs",
                                    url,
                                    resp.status,
                                    delay,
                                )
                                await asyncio.sleep(delay)
                                continue
                            endpoint_failed = True
                            break
                        if attempt < RETRIES:
                            delay = RETRY_INIT_DELAY * RETRY_FACTOR ** (attempt - 1)
                            _LOGGER.debug(
                                "Token endpoint %s returned %s, retrying in %.1fs",
                                url,
                                resp.status,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        connection_error = f"Token endpoint {url} failed: {resp.status}"
                        endpoint_failed = True
                        break
                except (TimeoutError, aiohttp.ClientError) as err:
                    if attempt < RETRIES:
                        await asyncio.sleep(
                            RETRY_INIT_DELAY * RETRY_FACTOR ** (attempt - 1)
                        )
                        continue
                    connection_error = str(err)
                    endpoint_failed = True
                    break
            if endpoint_failed:
                continue
        if connection_error:
            raise ZaptecConnectionError(connection_error)
        raise ZaptecAuthError(auth_error or "Invalid credentials")

    async def async_request(
        self,
        method: str,
        path: str,
        json: Any | None = None,
        authenticated: bool = True,
    ) -> Any:
        """Perform a request against the Zaptec API and return parsed JSON."""
        delay = RETRY_INIT_DELAY
        reauthenticated = False
        for attempt in range(1, RETRIES + 1):
            headers = {"Accept": "application/json"}
            if authenticated:
                if self._token is None:
                    self._token = await self.async_get_access_token()
                headers["Authorization"] = f"Bearer {self._token}"
            try:
                async with self._session.request(
                    method,
                    API_URL + path,
                    headers=headers,
                    json=json,
                ) as resp:
                    if resp.status == 401 and authenticated and not reauthenticated:
                        # Token expired: log in again and retry once.
                        reauthenticated = True
                        self._token = await self.async_get_access_token()
                        continue
                    if resp.status == 401 and authenticated:
                        self._token = None
                        raise ZaptecAuthError("Invalid credentials")
                    if resp.status in RETRYABLE_STATUSES and attempt < RETRIES:
                        _LOGGER.debug(
                            "Zaptec API %s %s -> %s, retrying in %.1fs",
                            method,
                            path,
                            resp.status,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        delay *= RETRY_FACTOR
                        continue
                    if resp.status in RETRYABLE_STATUSES:
                        raise ZaptecConnectionError(
                            f"Zaptec API {method} {path} temporarily unavailable: {resp.status}"
                        )
                    text = await resp.text()
                    if resp.status >= 400:
                        raise ZaptecApiError(
                            f"Zaptec API {method} {path} failed: {resp.status} {text[:200]}"
                        )
                    if not text:
                        return {}
                    try:
                        return _normalize(await resp.json(content_type=None))
                    except (aiohttp.ContentTypeError, ValueError) as err:
                        raise ZaptecApiError(
                            f"Zaptec API {method} {path} returned invalid JSON"
                        ) from err
            except (TimeoutError, aiohttp.ClientError) as err:
                if attempt < RETRIES:
                    await asyncio.sleep(delay)
                    delay *= RETRY_FACTOR
                    continue
                raise ZaptecConnectionError("Error connecting to Zaptec API") from err
        raise ZaptecConnectionError(f"Zaptec API {method} {path} exhausted retries")

    async def async_get(self, path: str) -> Any:
        """GET a resource."""
        return await self.async_request("GET", path)

    async def async_post(self, path: str, json: Any | None = None) -> Any:
        """POST to a resource."""
        return await self.async_request("POST", path, json=json or {})

    def invalidate_token(self) -> None:
        """Forget the cached token (forces re-authentication)."""
        self._token = None
