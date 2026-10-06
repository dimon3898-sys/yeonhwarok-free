"""Base HTTP client for gcube CLI."""

from __future__ import annotations

import base64
import functools
import json
import sys
import time
from typing import Any, cast

import click
import httpx

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Raised on HTTP 401 — token expired or invalid."""

    MESSAGE = (
        "Token expired or invalid. "
        "Please get a new token from https://gcube.ai"
    )

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)


class APIError(Exception):
    """Raised when the gcube API returns status != 200 in the response body."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"API Error [{code}]: {message}")


# ---------------------------------------------------------------------------
# Command-layer decorator
# ---------------------------------------------------------------------------


def handle_api_errors(func: Any) -> Any:
    """Decorator that catches AuthError / APIError and exits with the correct code.

    Apply to every Click command that calls the API.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AuthError as e:
            click.echo(str(e), err=True)
            sys.exit(3)
        except APIError as e:
            click.echo(f"API Error [{e.code}]: {e.message}", err=True)
            sys.exit(2)

    return wrapper


# ---------------------------------------------------------------------------
# Retry configuration (aligned with ky defaults used by the web console)
# ---------------------------------------------------------------------------

_RETRY_METHODS = frozenset({"GET", "PUT", "DELETE", "HEAD", "OPTIONS"})
_RETRY_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_MAX_RETRIES = 2
_RETRY_DELAY = 0.3  # base delay in seconds; doubles each retry


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _make_debug_hooks(base_url: str) -> dict[str, list[Any]]:
    """Return httpx event hooks that print request/response to stderr."""
    import json as _json

    def _pretty(raw: str) -> str:
        try:
            return _json.dumps(_json.loads(raw), ensure_ascii=False, indent=2)
        except (ValueError, TypeError):
            return raw

    def _log_request(request: httpx.Request) -> None:
        click.echo(f"\n[DEBUG] >>> {request.method} {request.url}", err=True)
        if request.content:
            click.echo("[DEBUG] >>> Body:", err=True)
            click.echo(_pretty(request.content.decode("utf-8", errors="replace")), err=True)

    def _log_response(response: httpx.Response) -> None:
        response.read()
        click.echo(f"[DEBUG] <<< {response.status_code}", err=True)
        click.echo("[DEBUG] <<< Body:", err=True)
        click.echo(_pretty(response.text), err=True)

    return {"request": [_log_request], "response": [_log_response]}


class Client:
    """Synchronous HTTP client with Bearer auth and uniform error handling."""

    def __init__(self, base_url: str, token: str, debug: bool = False) -> None:
        self.base_url = base_url
        self.debug = debug
        init_kwargs: dict[str, Any] = {
            "base_url": base_url,
            "headers": {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            "timeout": 60.0,
        }
        if debug:
            init_kwargs["event_hooks"] = _make_debug_hooks(base_url)
        self._client = httpx.Client(**init_kwargs)

    # ------------------------------------------------------------------
    # Internal request dispatcher
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Execute an HTTP request and return the parsed JSON body.

        Error handling order:
        1. httpx.RequestError (network/timeout)         → retry then sys.exit(4)
        2. Retriable status code (5xx + 408/429)        → retry then raise APIError
        3. HTTP 401                                     → raise AuthError
        4. raise_for_status() for other 4xx/5xx         → wrap as APIError
        5. body["status"] != 200                        → raise APIError

        Idempotent methods (GET/PUT/DELETE) retry up to 2 times on transient
        errors with exponential backoff, matching the web console's ky defaults.
        POST is never retried to prevent duplicate resource creation.

        Note: 429 responses use the same fixed backoff; Retry-After header is
        not honoured.  Acceptable for a CLI but worth revisiting if 429 rate
        limiting becomes common in production.
        """
        retries = _MAX_RETRIES if method.upper() in _RETRY_METHODS else 0

        for attempt in range(1 + retries):
            if attempt > 0:
                time.sleep(_RETRY_DELAY * (2 ** (attempt - 1)))

            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.TimeoutException:
                if attempt < retries:
                    continue
                click.echo(
                    f"Request timed out: {method} {path}. "
                    f"Server may be busy, please retry.",
                    err=True,
                )
                sys.exit(4)
            except httpx.RequestError:
                if attempt < retries:
                    continue
                click.echo(
                    f"Cannot connect to {self.base_url} ({method} {path}). "
                    f"Check network.",
                    err=True,
                )
                sys.exit(4)

            # Retriable HTTP status → retry before raising
            if response.status_code in _RETRY_STATUS_CODES and attempt < retries:
                continue

            break

        # 401 — try to parse body first; only raise AuthError for bare token failures
        if response.status_code == 401:
            try:
                err_data = cast(dict[str, Any], response.json())
                if "error" in err_data and "message" in err_data:
                    raise APIError(
                        err_data.get("status", 401),
                        err_data.get("error", "UNAUTHORIZED"),
                        err_data.get("message", "Unauthorized"),
                    )
            except (ValueError, KeyError):
                pass
            raise AuthError()

        # Other unexpected HTTP-level errors (e.g. 500 with no JSON body)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Try to extract gcube envelope; fall back to generic message
            try:
                err_data = cast(dict[str, Any], exc.response.json())
                raise APIError(
                    err_data.get("status", exc.response.status_code),
                    err_data.get("error", str(exc.response.status_code)),
                    err_data.get("message", exc.response.text),
                ) from exc
            except (ValueError, KeyError):
                raise APIError(
                    exc.response.status_code,
                    str(exc.response.status_code),
                    exc.response.text,
                ) from exc

        # Parse gcube response envelope
        try:
            data: dict[str, Any] = cast(dict[str, Any], response.json())
        except ValueError as exc:
            raise APIError(
                response.status_code,
                "EMPTY_RESPONSE",
                "Server returned empty or invalid JSON body",
            ) from exc
        if data.get("status") != 200:
            raise APIError(
                data.get("status", 0),
                data.get("error", ""),
                data.get("message", "Unknown error"),
            )

        return data

    # ------------------------------------------------------------------
    # Public HTTP methods
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("GET", path, **kwargs)

    def post(
        self, path: str, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request("POST", path, json=json, **kwargs)

    def put(
        self, path: str, json: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return self._request("PUT", path, json=json, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self._request("DELETE", path, **kwargs)

    def get_quiet(
        self, path: str, *, timeout: float = 5.0, **kwargs: Any
    ) -> dict[str, Any] | None:
        """GET without retry, stderr output, or sys.exit.

        Returns parsed JSON on success (HTTP 200 + envelope status 200),
        or ``None`` on any failure.  Designed for best-effort lookups
        (e.g. credential auto-detection) that must never block the main flow.
        """
        try:
            response = self._client.get(path, timeout=timeout, **kwargs)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("status") != 200:
                return None
            return data
        except (Exception, SystemExit):
            return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_client(
    config: Any,  # gcube_cli.config.config.GcubeConfig — Any to avoid circular import
    debug: bool = False,
    platform_url: str | None = None,
) -> Client:
    """Create a Client from a loaded GcubeConfig object.

    Exits with code 1 if no token is configured.
    """
    token: str | None = None
    if config.auth:
        token = config.auth.access_token or None

    if not token:
        click.echo(
            "No token configured. Run: gcube auth login",
            err=True,
        )
        sys.exit(1)

    base_url = platform_url or config.platform_url or "https://api.gcube.ai"
    return Client(base_url=base_url, token=token, debug=debug)


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Decode JWT payload without signature verification. Returns None on failure."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return None


def decode_email_from_jwt(token: str) -> str | None:
    """Extract email (or email-like sub) claim from a JWT without verification."""
    payload = decode_jwt_payload(token)
    if payload is None:
        return None
    email = payload.get("email")
    if not email:
        sub = payload.get("sub", "")
        if "@" in str(sub):
            email = sub
    return email or None


def make_client_from_ctx(ctx: click.Context) -> Client:
    """Create a Client from a Click context populated by the CLI entry point."""
    gcube_ctx = ctx.obj
    if not gcube_ctx.token:
        click.echo(
            "No token configured. Run: gcube auth login",
            err=True,
        )
        sys.exit(1)
    return Client(
        base_url=gcube_ctx.platform_url,
        token=gcube_ctx.token,
        debug=gcube_ctx.debug,
    )
