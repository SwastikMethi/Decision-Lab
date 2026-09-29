import pytest

from repo_mcp import api_client, config

BASE = "http://127.0.0.1:8000"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TARGET_API_BASE_URL", BASE)
    monkeypatch.setenv("TARGET_API_TOKEN", "test-token-not-real")
    config.get_settings.cache_clear()
    api_client.get_client.cache_clear()
    yield
    config.get_settings.cache_clear()
    api_client.get_client.cache_clear()
