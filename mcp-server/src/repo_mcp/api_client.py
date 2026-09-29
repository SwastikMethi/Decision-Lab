# generated-by: generate-mcp source_hash=a333806c00d6
"""HTTP client for the target API. Every tool call goes through ApiClient.request.

Safety behaviour lives here on purpose: http/https only, link-local and cloud-metadata
destinations blocked, redirects off, bounded timeout, response size cap, header and
token redaction in every error. tools.py must not bypass this module.
"""
from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from .config import get_settings

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token", "proxy-authorization"}
BLOCKED_HOSTS = {"metadata.google.internal", "metadata", "169.254.169.254", "100.100.100.200", "fd00:ec2::254"}
TOKEN_SHAPES = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{16,}")
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ApiError(ToolError):
    """Raised for any failed upstream call. The message is safe to show to the model.

    Subclasses the SDK's ToolError on purpose: mcp 2.x shows the model only
    "Error executing tool <name>" for any other exception type, which hides the
    redacted status and body we worked to produce. As a ToolError the message
    below reaches the model verbatim and the server logs it without a traceback.
    """

    def __init__(self, category: str, message: str, status: int | None = None):
        self.category = category
        self.status = status
        self.safe_message = message
        super().__init__(str(self))

    def __str__(self) -> str:
        code = f" (HTTP {self.status})" if self.status is not None else ""
        return f"{self.category}{code}: {self.safe_message}"


def redact(text: str) -> str:
    """Strip token shapes from free text before it reaches an error or log."""
    return TOKEN_SHAPES.sub(lambda m: (m.group(1) or "") + "[REDACTED]", text or "")


def redact_mapping(data: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive keys in a JSON-like structure."""
    if depth > 6:
        return data
    if isinstance(data, dict):
        return {k: ("[REDACTED]" if k.lower() in SENSITIVE_HEADERS | {"password", "secret", "token", "api_key", "apikey", "access_token", "refresh_token"} else redact_mapping(v, depth + 1)) for k, v in data.items()}
    if isinstance(data, list):
        return [redact_mapping(v, depth + 1) for v in data]
    if isinstance(data, str):
        return redact(data)
    return data


def assert_safe_destination(url: str) -> None:
    u = urlparse(url)
    if u.scheme not in {"http", "https"}:
        raise ApiError("blocked_destination", "only http and https URLs are allowed")
    host = (u.hostname or "").lower().rstrip(".")
    if not host:
        raise ApiError("blocked_destination", "URL has no host")
    if host in BLOCKED_HOSTS:
        raise ApiError("blocked_destination", f"destination {host} is blocked")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_link_local or (ip.version == 6 and str(ip).startswith("fe80")):
        raise ApiError("blocked_destination", f"link-local destination {host} is blocked")


class ApiClient:
    def __init__(self, base_url: str, token: str | None, timeout: float, max_bytes: int):
        assert_safe_destination(base_url)
        self._base_url = base_url.rstrip("/")
        self._max_bytes = max_bytes
        headers = {"Accept": "application/json", "User-Agent": "repo-mcp/0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            transport=httpx.AsyncHTTPTransport(retries=0),
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        path_params: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        json: Any = None,
    ) -> dict:
        """Call one API operation and return its JSON as a dict.

        path is a template such as "/users/{user_id}". path_params are URL-encoded into it.
        query values that are None are dropped. Non-dict JSON responses are wrapped as {"result": ...}.
        """
        method = method.upper()
        url_path = path
        for k, v in (path_params or {}).items():
            if v is None or v == "":
                raise ApiError("invalid_input", f"path parameter {k!r} is required")
            url_path = url_path.replace("{" + k + "}", quote(str(v), safe=""))
        if "{" in url_path:
            missing = re.findall(r"{(\w+)}", url_path)
            raise ApiError("invalid_input", f"missing path parameter(s): {', '.join(missing)}")
        params = {k: v for k, v in (query or {}).items() if v is not None}
        try:
            resp = await self._client.request(method, url_path, params=params or None, json=json)
        except httpx.TimeoutException:
            raise ApiError("timeout", f"{method} {url_path} timed out") from None
        except httpx.HTTPError as e:
            raise ApiError("network", redact(f"{method} {url_path} failed: {type(e).__name__}")) from None

        body = resp.content
        if len(body) > self._max_bytes:
            raise ApiError(
                "response_too_large",
                f"{method} {url_path} returned {len(body):,} bytes; this server returns at most {self._max_bytes:,}. "
                "Use a narrower tool or filter if one exists, or raise MAX_RESPONSE_BYTES for this server.",
                resp.status_code,
            )
        if resp.status_code >= 400:
            category = {401: "unauthorized", 403: "forbidden", 404: "not_found", 422: "validation_error", 429: "rate_limited"}.get(resp.status_code, "upstream_error")
            snippet = redact(body[:300].decode("utf-8", errors="replace"))
            raise ApiError(category, f"{method} {url_path} -> {snippet or 'no body'}", resp.status_code)
        if resp.status_code == 204 or not body:
            return {"status": resp.status_code}
        try:
            data = resp.json()
        except ValueError:
            return {"status": resp.status_code, "text": redact(body[: self._max_bytes].decode("utf-8", errors="replace"))}
        data = redact_mapping(data)
        return data if isinstance(data, dict) else {"result": data}


@lru_cache(maxsize=1)
def get_client() -> ApiClient:
    s = get_settings()
    return ApiClient(
        base_url=s.target_api_base_url,
        token=s.target_api_token.get_secret_value() if s.target_api_token else None,
        timeout=s.target_api_timeout_seconds,
        max_bytes=s.max_response_bytes,
    )
