"""Contract checks for the local A -> B -> data-service -> PostgreSQL path.

These tests are intentionally source-level so they can run without Docker, a
collector, or a database. Runtime smoke/trace verification remains a separate
environment concern.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE_SOURCES = {
    "service-a": (ROOT / "service-a" / "main.py").read_text(encoding="utf-8"),
    "service-b": (ROOT / "service-b" / "main.py").read_text(encoding="utf-8"),
    "data-service": (ROOT / "data-service" / "main.py").read_text(encoding="utf-8"),
}


def test_all_services_expose_correlated_liveness_and_readiness():
    for source in SERVICE_SOURCES.values():
        assert '@app.get("/health")' in source
        assert '@app.get("/ready")' in source
        assert '"trace_id": current_trace_id()' in source
        assert 'response.headers["X-Trace-ID"]' in source
        assert 'content={"detail": exc.detail, "trace_id": current_trace_id()}' in source
        assert 'FastAPIInstrumentor.instrument_app' in source


def test_service_a_delegates_the_order_to_service_b_only():
    source = SERVICE_SOURCES["service-a"]
    assert 'SERVICE_B_URL = os.getenv("SERVICE_B_URL"' in source
    assert 'f"{SERVICE_B_URL}/order/{order_id}"' in source
    assert 'headers=outbound_headers()' in source
    assert 'DATA_SERVICE_URL' not in source
    assert "psycopg2" not in source
    assert "app_password" not in source


def test_service_b_is_the_http_boundary_before_data_service():
    source = SERVICE_SOURCES["service-b"]
    assert 'DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL"' in source
    assert '"order.data_service.order.call"' in source
    assert '"order.data_service.inventory.call"' in source
    assert '"inventory.data_service.call"' in source
    assert 'inject(headers)' in source
    assert 'headers=outbound_headers()' in source
    assert "psycopg2" not in source
    assert "app_password" not in source


def test_data_service_owns_database_spans_and_uses_current_db_attributes():
    source = SERVICE_SOURCES["data-service"]
    assert "Psycopg2Instrumentor" in source
    assert '"data.db.fetch"' in source
    assert '"health.db.check"' in source
    assert '"db.system.name": "postgresql"' in source
    assert '"db.operation.name": "SELECT"' in source
    assert 'cursor.execute(query, (record_id,))' in source
    assert "app_password" not in source


def test_trace_id_is_not_used_as_a_metric_attribute():
    for source in SERVICE_SOURCES.values():
        metric_lines = [line for line in source.splitlines() if ".add(" in line or ".record(" in line]
        assert all("trace_id" not in line for line in metric_lines)
