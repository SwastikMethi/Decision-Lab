"""Invariant safety tests for api_client. generate-mcp ships these; do not weaken them."""
import httpx
import pytest
import respx

from repo_mcp.api_client import ApiClient, ApiError, assert_safe_destination, get_client, redact

BASE = "http://127.0.0.1:8000"  # must match conftest._env


@respx.mock
async def test_path_substitution_and_query_and_auth_header():
    route = respx.get(f"{BASE}/users/a%2Fb").mock(return_value=httpx.Response(200, json={"id": "a/b"}))
    data = await get_client().request("GET", "/users/{user_id}", path_params={"user_id": "a/b"}, query={"limit": 5, "q": None})
    assert data == {"id": "a/b"}
    req = route.calls.last.request
    assert req.url.params["limit"] == "5"
    assert "q" not in req.url.params
    assert req.headers["Authorization"] == "Bearer test-token-not-real"


@respx.mock
async def test_json_body_is_sent_for_writes():
    route = respx.post(f"{BASE}/users").mock(return_value=httpx.Response(201, json={"id": "u1"}))
    data = await get_client().request("POST", "/users", json={"email": "a@b.c", "name": "A"})
    assert data["id"] == "u1"
    assert route.calls.last.request.content == b'{"email":"a@b.c","name":"A"}'


async def test_missing_path_param_is_rejected_before_any_request():
    with pytest.raises(ApiError) as e:
        await get_client().request("GET", "/users/{user_id}")
    assert e.value.category == "invalid_input"


@respx.mock
async def test_non_2xx_maps_to_category_and_redacts_body():
    respx.get(f"{BASE}/users/x").mock(return_value=httpx.Response(404, json={"detail": "not found", "token": "Bearer abcdefghijklmnop"}))
    with pytest.raises(ApiError) as e:
        await get_client().request("GET", "/users/{user_id}", path_params={"user_id": "x"})
    assert e.value.category == "not_found"
    assert e.value.status == 404
    assert "abcdefghijklmnop" not in str(e.value)
    assert "[REDACTED]" in str(e.value)


@respx.mock
async def test_timeout_is_a_safe_error():
    respx.get(f"{BASE}/slow").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(ApiError) as e:
        await get_client().request("GET", "/slow")
    assert e.value.category == "timeout"


@respx.mock
async def test_response_size_cap():
    respx.get(f"{BASE}/big").mock(return_value=httpx.Response(200, content=b"x" * 300_000))
    with pytest.raises(ApiError) as e:
        await get_client().request("GET", "/big")
    assert e.value.category == "response_too_large"


@respx.mock
async def test_sensitive_keys_redacted_recursively_and_lists_wrapped():
    respx.get(f"{BASE}/me").mock(return_value=httpx.Response(200, json={"user": {"password": "p", "api_key": "k"}, "ok": True}))
    data = await get_client().request("GET", "/me")
    assert data["user"] == {"password": "[REDACTED]", "api_key": "[REDACTED]"}
    respx.get(f"{BASE}/list").mock(return_value=httpx.Response(200, json=[1, 2]))
    assert await get_client().request("GET", "/list") == {"result": [1, 2]}


@respx.mock
async def test_204_returns_status_only():
    respx.delete(f"{BASE}/users/x").mock(return_value=httpx.Response(204))
    assert await get_client().request("DELETE", "/users/{user_id}", path_params={"user_id": "x"}) == {"status": 204}


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data",
    "http://metadata.google.internal/computeMetadata",
    "http://[fe80::1]/",
    "ftp://example.com/",
    "file:///etc/passwd",
])
def test_blocked_destinations(url):
    with pytest.raises(ApiError) as e:
        assert_safe_destination(url)
    assert e.value.category == "blocked_destination"


def test_client_refuses_blocked_base_url():
    with pytest.raises(ApiError):
        ApiClient("http://169.254.169.254", None, 5, 1000)


def test_redact_token_shapes():
    assert redact("Authorization: Bearer abcdefghijklmnop") == "Authorization: Bearer [REDACTED]"
    assert redact("key sk-abcdefghijklmnopqrstuvwxyz") == "key [REDACTED]"  # fake shape, exercises the sk- rule
