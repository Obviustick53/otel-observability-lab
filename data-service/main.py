"""Observable data service for the local OTel laboratory.

The service reads the existing ``orders`` and ``inventory`` tables. Database
queries are deliberately kept in this module so the SQL is parameterized and
never sent to logs or custom telemetry attributes.
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote, urlsplit

import psycopg2
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode
from pythonjsonlogger import jsonlogger
from starlette.concurrency import run_in_threadpool


SERVICE_NAME_VALUE = os.getenv("OTEL_SERVICE_NAME", "data-service")
SERVICE_VERSION_VALUE = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "observability")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    if db_host and db_user and db_password:
        DATABASE_URL = (
            f"postgresql://{quote(db_user, safe='')}:{quote(db_password, safe='')}"
            f"@{db_host}:{db_port}/{db_name}"
        )
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
SDK_DISABLED = os.getenv("OTEL_SDK_DISABLED", "false").lower() in {"1", "true", "yes"}

resource = Resource.create(
    {
        SERVICE_NAME: SERVICE_NAME_VALUE,
        SERVICE_VERSION: SERVICE_VERSION_VALUE,
        "deployment.environment": ENVIRONMENT,
        "service.namespace": "otel-lab",
    }
)

tracer_provider: TracerProvider | None = None
meter_provider: MeterProvider | None = None
logger_provider: LoggerProvider | None = None

if not SDK_DISABLED:
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    latency_buckets = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True),
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
        views=[
            View(
                instrument_name="app_request_duration_seconds",
                aggregation=ExplicitBucketHistogramAggregation(boundaries=latency_buckets),
            ),
            View(
                instrument_name="app_db_duration_seconds",
                aggregation=ExplicitBucketHistogramAggregation(boundaries=latency_buckets),
            ),
        ],
    )
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTLP_ENDPOINT, insecure=True))
    )
    set_logger_provider(logger_provider)

    Psycopg2Instrumentor().instrument()


tracer = trace.get_tracer(SERVICE_NAME_VALUE)
meter = metrics.get_meter(SERVICE_NAME_VALUE)

# RED/USE instruments. Attribute values are intentionally bounded to avoid
# high-cardinality metric labels (for example, no order or product id).
requests_total = meter.create_counter(
    "app_requests",
    unit="1",
    description="Total de solicitudes procesadas por data-service",
)
request_duration = meter.create_histogram(
    "app_request_duration_seconds",
    unit="s",
    description="Latencia de solicitudes de data-service",
)
active_requests = meter.create_up_down_counter(
    "app_active_requests",
    unit="1",
    description="Solicitudes activas en data-service",
)
db_duration = meter.create_histogram(
    "app_db_duration_seconds",
    unit="s",
    description="Latencia de consultas PostgreSQL",
)
db_operations_total = meter.create_counter(
    "app_db_operations",
    unit="1",
    description="Operaciones PostgreSQL completadas por data-service",
)


class TraceJsonFormatter(jsonlogger.JsonFormatter):
    """Emit structured logs with the active W3C trace context."""

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        context = trace.get_current_span().get_span_context()
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["service"] = SERVICE_NAME_VALUE
        log_record["environment"] = ENVIRONMENT
        log_record["trace_id"] = format(context.trace_id, "032x") if context.is_valid else None
        log_record["span_id"] = format(context.span_id, "016x") if context.is_valid else None


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(TraceJsonFormatter())
    root.addHandler(stdout_handler)

    if logger_provider is not None:
        root.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))


configure_logging()
logger = logging.getLogger(SERVICE_NAME_VALUE)


def current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


def parse_error_rate(raw_value: str | None) -> float:
    """Validate the only chaos control exposed by this service."""

    if raw_value is None or not raw_value.strip():
        return 0.0
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("LAB_DATA_ERROR_RATE must be a number between 0 and 1") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError("LAB_DATA_ERROR_RATE must be between 0 and 1")
    return value


def configured_error_rate() -> float:
    """Read the setting per request so setting it back to 0 is reversible."""

    return parse_error_rate(os.getenv("LAB_DATA_ERROR_RATE"))


def database_target(database_url: str) -> dict[str, Any]:
    """Return non-secret DB attributes for spans; never return user/password."""

    parsed = urlsplit(database_url)
    return {
        "db.system.name": "postgresql",
        "db.namespace": parsed.path.lstrip("/") or "unknown",
        "server.address": parsed.hostname or "unknown",
        "server.port": parsed.port or 5432,
    }


DataKind = Literal["order", "inventory"]


class DatabaseConfigurationError(RuntimeError):
    """Raised when the service has no safe database configuration."""


def fetch_record(kind: DataKind, record_id: str) -> dict[str, Any] | None:
    """Fetch one record using the existing lab schema and parameter binding."""

    if not DATABASE_URL:
        raise DatabaseConfigurationError("DATABASE_URL is not configured")

    if kind == "order":
        query = (
            "SELECT order_id, customer_id, product_id, quantity, status "
            "FROM orders WHERE order_id = %s"
        )
        columns = ("order_id", "customer_id", "product_id", "quantity", "status")
        table = "orders"
    else:
        query = (
            "SELECT product_id, available, warehouse, updated_at "
            "FROM inventory WHERE product_id = %s"
        )
        columns = ("product_id", "available", "warehouse", "updated_at")
        table = "inventory"

    started = time.perf_counter()
    with tracer.start_as_current_span(
        "data.db.fetch",
        kind=SpanKind.CLIENT,
        attributes={
            **database_target(DATABASE_URL),
            "db.operation.name": "SELECT",
            "db.collection.name": table,
            "data.record.type": kind,
        },
    ) as span:
        try:
            # The query and its value are intentionally absent from telemetry;
            # psycopg2 receives the value through a parameterized execute call.
            with psycopg2.connect(DATABASE_URL, connect_timeout=3) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (record_id,))
                    row = cursor.fetchone()
            db_operations_total.add(1, {"operation": "select", "record_type": kind, "outcome": "success"})
            if row is None:
                span.set_status(Status(StatusCode.OK))
                return None
            result = dict(zip(columns, row))
            if kind == "inventory" and result["updated_at"] is not None:
                result["updated_at"] = result["updated_at"].isoformat()
            span.set_status(Status(StatusCode.OK))
            return result
        except Exception as exc:
            db_operations_total.add(1, {"operation": "select", "record_type": kind, "outcome": "error"})
            # Do not attach driver messages, SQL, DSNs or bound values to the
            # span. The exception class is enough for operational grouping.
            span.set_attribute("error.type", type(exc).__name__)
            span.set_status(Status(StatusCode.ERROR, "database operation failed"))
            raise
        finally:
            db_duration.record(time.perf_counter() - started, {"operation": "select", "record_type": kind})


def check_database_ready() -> None:
    """Run a minimal readiness query without exposing SQL or credentials."""

    if not DATABASE_URL:
        raise DatabaseConfigurationError("DATABASE_URL is not configured")
    with psycopg2.connect(DATABASE_URL, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()


def kind_for_record_id(record_id: str) -> DataKind:
    """Resolve the untyped endpoint used by simple clients in this lab."""

    return "order" if record_id.startswith("ord-") else "inventory"


def maybe_inject_error(kind: DataKind) -> None:
    """Inject a controlled 503 only when LAB_DATA_ERROR_RATE requests it."""

    rate = configured_error_rate()
    if rate and random.random() < rate:
        with tracer.start_as_current_span(
            "data.business.chaos_inject_error",
            attributes={"data.record.type": kind, "chaos.control": "LAB_DATA_ERROR_RATE", "chaos.rate": rate},
        ) as span:
            span.set_status(Status(StatusCode.ERROR, "controlled laboratory fault"))
            logger.warning(
                "controlled data error injected",
                extra={"operation": "data_read", "record_type": kind, "chaos_rate": rate},
            )
            raise HTTPException(status_code=503, detail="temporary data-service failure")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service started", extra={"otel_enabled": not SDK_DISABLED, "database_configured": bool(DATABASE_URL)})
    yield
    if tracer_provider is not None:
        tracer_provider.shutdown()
    if meter_provider is not None:
        meter_provider.shutdown()
    if logger_provider is not None:
        logger_provider.shutdown()


app = FastAPI(title="OTel Lab - Data Service", version=SERVICE_VERSION_VALUE, lifespan=lifespan)
if not SDK_DISABLED:
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


async def read_typed_data(
    record_id: str,
    kind: DataKind,
    envelope: str,
    route_template: str,
) -> dict[str, Any]:
    """Shared handler that preserves consistent spans, metrics and errors."""

    started = time.perf_counter()
    active_requests.add(1)
    status_code = "200"
    try:
        with tracer.start_as_current_span(
            "data.business.read",
            attributes={"data.record.type": kind, "data.lookup.mode": "parameterized_id"},
        ) as span:
            if not record_id.strip():
                status_code = "400"
                span.set_status(Status(StatusCode.ERROR, "empty record id"))
                raise HTTPException(status_code=400, detail="record_id must not be empty")
            maybe_inject_error(kind)
            result = await run_in_threadpool(fetch_record, kind, record_id)
            if result is None:
                status_code = "404"
                span.set_status(Status(StatusCode.OK, "record not found"))
                logger.info("data record not found", extra={"operation": "data_read", "record_type": kind})
                raise HTTPException(status_code=404, detail="Data record not found")
            span.set_attribute("data.result", "found")
            span.set_status(Status(StatusCode.OK))

        logger.info("data record returned", extra={"operation": "data_read", "record_type": kind})
        return {envelope: result, "record_type": kind, "trace_id": current_trace_id()}
    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except DatabaseConfigurationError as exc:
        status_code = "503"
        logger.error("database configuration unavailable", extra={"operation": "data_read", "record_type": kind})
        raise HTTPException(status_code=503, detail="Data service database is not configured") from exc
    except Exception as exc:
        status_code = "500"
        logger.exception("data read failed", extra={"operation": "data_read", "record_type": kind})
        raise HTTPException(status_code=500, detail="Data service internal error") from exc
    finally:
        labels = {
            "http.request.method": "GET",
            "http.route": route_template,
            "http.response.status_code": status_code,
        }
        requests_total.add(1, labels)
        request_duration.record(time.perf_counter() - started, labels)
        active_requests.add(-1)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness endpoint; database readiness is intentionally separate from liveness."""

    return {"status": "ok", "service": SERVICE_NAME_VALUE, "trace_id": current_trace_id()}


@app.middleware("http")
async def add_trace_id_header(request: Request, call_next):
    response = await call_next(request)
    trace_id = current_trace_id()
    if trace_id:
        response.headers["X-Trace-ID"] = trace_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "trace_id": current_trace_id()},
        headers=exc.headers,
    )


@app.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness verifies database connectivity; liveness remains dependency-free."""

    with tracer.start_as_current_span(
        "health.db.check",
        kind=SpanKind.CLIENT,
        attributes={"db.system.name": "postgresql", "db.operation.name": "SELECT"},
    ) as span:
        try:
            await run_in_threadpool(check_database_ready)
            span.set_status(Status(StatusCode.OK))
            return {"status": "ready", "service": SERVICE_NAME_VALUE, "trace_id": current_trace_id()}
        except DatabaseConfigurationError as exc:
            span.set_status(Status(StatusCode.ERROR, "database is not configured"))
            raise HTTPException(status_code=503, detail="Data service database is not configured") from exc
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "database is not ready"))
            raise HTTPException(status_code=503, detail="Data service database is not ready") from exc


@app.get("/data/{record_id}")
async def read_data(record_id: str) -> dict[str, Any]:
    """Return an order or inventory record using the current lab identifiers."""

    kind = kind_for_record_id(record_id)
    return await read_typed_data(record_id, kind, "data", "/data/{record_id}")


@app.get("/order/{order_id}")
async def read_order(order_id: str) -> dict[str, Any]:
    """Compatibility alias for clients that address the current order flow."""

    return await read_typed_data(order_id, "order", "order", "/order/{order_id}")


@app.get("/inventory/{product_id}")
async def read_inventory(product_id: str) -> dict[str, Any]:
    """Compatibility alias for the existing inventory flow."""

    return await read_typed_data(product_id, "inventory", "inventory", "/inventory/{product_id}")
