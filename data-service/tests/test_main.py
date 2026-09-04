import os
import sys
from pathlib import Path

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def test_parse_error_rate_defaults_to_zero_and_accepts_ten_percent():
    assert main.parse_error_rate(None) == 0.0
    assert main.parse_error_rate("0.10") == 0.10


@pytest.mark.parametrize("raw_value", ["-0.1", "1.1", "not-a-rate"])
def test_parse_error_rate_rejects_invalid_values(raw_value):
    with pytest.raises(ValueError):
        main.parse_error_rate(raw_value)


def test_health_is_live_without_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "data-service"


def test_database_target_excludes_credentials():
    attributes = main.database_target("postgresql://user:secret@db.example:5432/observability")
    assert attributes["server.address"] == "db.example"
    assert "secret" not in str(attributes)


def test_data_returns_503_when_database_is_not_configured(client, monkeypatch):
    monkeypatch.setattr(main, "DATABASE_URL", None)
    response = client.get("/data/ord-001")
    assert response.status_code == 503
    assert response.json()["detail"] == "Data service database is not configured"


def test_data_endpoint_returns_existing_order_shape(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "fetch_record",
        lambda kind, record_id: {
            "order_id": record_id,
            "customer_id": "cust-test",
            "product_id": "keyboard",
            "quantity": 1,
            "status": "confirmed",
        },
    )
    response = client.get("/data/ord-001")
    body = response.json()
    assert response.status_code == 200
    assert body["record_type"] == "order"
    assert body["data"]["order_id"] == "ord-001"
    assert body["trace_id"] is None


def test_compatibility_aliases_use_expected_tables(client, monkeypatch):
    seen = []

    def fake_fetch(kind, record_id):
        seen.append((kind, record_id))
        return {"product_id": record_id, "available": 1, "warehouse": "test"}

    monkeypatch.setattr(main, "fetch_record", fake_fetch)
    response = client.get("/inventory/keyboard")
    assert response.status_code == 200
    assert response.json()["inventory"]["product_id"] == "keyboard"
    assert seen == [("inventory", "keyboard")]


def test_missing_record_is_not_found(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_record", lambda kind, record_id: None)
    response = client.get("/data/ord-404")
    assert response.status_code == 404
    assert response.json()["detail"] == "Data record not found"


def test_chaos_control_is_reversible_and_returns_503(client, monkeypatch):
    monkeypatch.setenv("LAB_DATA_ERROR_RATE", "1")
    monkeypatch.setattr(main, "fetch_record", lambda kind, record_id: pytest.fail("DB must not be called"))
    injected = client.get("/data/ord-001")
    assert injected.status_code == 503

    monkeypatch.setenv("LAB_DATA_ERROR_RATE", "0")
    monkeypatch.setattr(main, "fetch_record", lambda kind, record_id: {"order_id": record_id})
    recovered = client.get("/data/ord-001")
    assert recovered.status_code == 200
