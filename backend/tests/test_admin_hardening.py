from fastapi.testclient import TestClient
import pytest

from app.config import Settings, get_settings
from app.main import app


def test_admin_readiness_reports_disabled_providers_as_safe() -> None:
    client = TestClient(app)

    response = client.get("/admin/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["mock_mode"] is True
    assert all(provider["outbound_actions_allowed"] is False for provider in payload["providers"])
    assert payload["safety"]["provider_failure_triggers_outbound"] is False
    assert payload["observability"]["audit_log_enabled"] is True


def test_admin_readiness_reports_missing_enabled_provider_as_degraded_safe(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("ENABLE_REAL_SEARCH", "true")
    monkeypatch.setenv("EXA_API_KEY", "")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        response = client.get("/admin/readiness")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded_safe"
    search_provider = next(provider for provider in payload["providers"] if provider["provider"] == "search:exa")
    assert search_provider["enabled"] is True
    assert search_provider["configured"] is False
    assert search_provider["outbound_actions_allowed"] is False


def test_health_check_includes_hardening_warnings(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("ENABLE_REAL_SEARCH", "true")
    monkeypatch.setenv("EXA_API_KEY", "")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert "Real search is enabled but EXA_API_KEY is missing." in response.json()["hardening_warnings"]


def test_production_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValueError, match="Production CORS origins must be explicit"):
        Settings(app_env="production", cors_origins=["*"])
