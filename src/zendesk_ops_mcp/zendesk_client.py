"""Zendesk API client wrapping httpx.AsyncClient."""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx


class ZendeskAPIError(Exception):
    """Raised when the Zendesk API returns an error response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class ZendeskClient:
    """Async Zendesk API client with pagination, rate limiting, and error handling."""

    def __init__(
        self,
        subdomain: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self._subdomain = subdomain if subdomain is not None else os.environ.get("ZENDESK_SUBDOMAIN", "")
        self._email = email if email is not None else os.environ.get("ZENDESK_EMAIL", "")
        self._api_token = api_token if api_token is not None else os.environ.get("ZENDESK_API_TOKEN", "")

        self._configured: bool = bool(self._subdomain and self._email and self._api_token)
        self.rate_limit_remaining: int | None = None

        # Build auth header: email/token:api_token base64-encoded
        credentials = f"{self._email}/token:{self._api_token}"
        encoded = base64.b64encode(credentials.encode()).decode()

        base_url = f"https://{self._subdomain}.zendesk.com" if self._subdomain else "https://zendesk.com"

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @classmethod
    def is_configured(cls) -> bool:
        """Check whether the required environment variables are all set."""
        return bool(
            os.environ.get("ZENDESK_SUBDOMAIN")
            and os.environ.get("ZENDESK_EMAIL")
            and os.environ.get("ZENDESK_API_TOKEN")
        )

    def _require_configured(self) -> None:
        """Raise ZendeskAPIError if the client is not configured."""
        if not self._configured:
            raise ZendeskAPIError(
                status_code=0,
                message=(
                    "Zendesk client is not configured. "
                    "Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, and ZENDESK_API_TOKEN."
                ),
            )

    def _update_rate_limit(self, response: httpx.Response) -> None:
        """Read X-RateLimit-Remaining from response headers."""
        header = response.headers.get("X-RateLimit-Remaining")
        if header is not None:
            try:
                self.rate_limit_remaining = int(header)
            except ValueError:
                pass

    def _check_response(self, response: httpx.Response) -> None:
        """Map HTTP error status codes to descriptive ZendeskAPIError exceptions."""
        if response.is_success:
            return

        status = response.status_code

        if status == 401:
            raise ZendeskAPIError(
                status_code=401,
                message="Invalid credentials. Check your ZENDESK_EMAIL and ZENDESK_API_TOKEN.",
            )
        elif status == 403:
            raise ZendeskAPIError(
                status_code=403,
                message="Insufficient permissions. This operation requires admin access.",
            )
        elif status == 404:
            raise ZendeskAPIError(
                status_code=404,
                message="Resource not found. Check the ID or endpoint.",
            )
        elif status == 422:
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise ZendeskAPIError(
                status_code=422,
                message=f"Validation error: {body}",
            )
        elif status == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise ZendeskAPIError(
                status_code=429,
                message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            )
        else:
            text = response.text[:200]
            raise ZendeskAPIError(
                status_code=status,
                message=f"Zendesk API error ({status}): {text}",
            )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Send a GET request and return the JSON response body."""
        self._require_configured()
        response = await self._client.get(path, params=params)
        self._update_rate_limit(response)
        self._check_response(response)
        return response.json()

    async def put(self, path: str, json: dict | None = None) -> dict:
        """Send a PUT request and return the JSON response body."""
        self._require_configured()
        response = await self._client.put(path, json=json)
        self._update_rate_limit(response)
        self._check_response(response)
        return response.json()

    async def get_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        data_key: str = "results",
    ) -> list[dict]:
        """Fetch all pages from a paginated Zendesk endpoint.

        Follows ``next_page`` URLs until exhausted.  ``data_key`` names the
        list field in each page response (e.g. "tickets", "users", "macros").
        """
        self._require_configured()
        results: list[dict] = []
        next_url: str | None = path

        # Build initial params; subsequent pages use absolute next_page URLs
        current_params = params

        while next_url:
            if next_url == path:
                response = await self._client.get(next_url, params=current_params)
            else:
                # next_page is a full URL; use httpx directly to avoid double base_url
                response = await self._client.get(next_url)

            self._update_rate_limit(response)
            self._check_response(response)

            body = response.json()
            page_items = body.get(data_key, [])
            results.extend(page_items)

            next_url = body.get("next_page")  # None when last page

        return results

    async def search(self, query: str) -> list[dict]:
        """Search Zendesk and return all matching results across all pages."""
        self._require_configured()
        results: list[dict] = []
        next_url: str | None = "/api/v2/search.json"
        params: dict[str, Any] | None = {"query": query, "per_page": 100}

        while next_url:
            if params is not None:
                response = await self._client.get(next_url, params=params)
                params = None  # only pass params on the first request
            else:
                response = await self._client.get(next_url)

            self._update_rate_limit(response)
            self._check_response(response)

            body = response.json()
            results.extend(body.get("results", []))
            next_url = body.get("next_page")

        return results

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
