"""Service B: consulta inventario en PostgreSQL."""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg2
from fastapi import FastAPI, HTTPException
from pythonjsonlogger import jsonlogger

from opentelemetry import metrics, trace
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
from opentelemetry._logs import set_logger_provider


SERVICE_NAME_VALUE = os.getenv("OTEL_SERVICE_NAME", "service-b")
SERVICE_VERSION_VALUE = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://app:app_password@localhost:5432/observability")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
SDK_DISABLED = os.getenv("OTEL_SDK_DISABLED", "false").lower() in {"1", "true", "yes"}

resource = Resource.create({
    SERVICE_NAME: SERVICE_NAME_VALUE,
    SERVICE_VERSION: SERVICE_VERSION_VALUE,
    "deployment.environment": ENVIRONMENT,
    "service.namespace": "otel-lab",
})

tracer_provider = None
meter_provider = None
logger_provider = None

if not SDK_DISABLED:
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True),
        export_interval_millis=5000,
    )
    latency_buckets = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
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

tracer = trace.get_tracer(SERVICE_NAME_VALUE)
meter = metrics.get_meter(SERVICE_NAME_VALUE)

requests_total = meter.create_counter(
    "app_requests",
    unit="1",
    description="Total de solicitudes procesadas por las aplicaciones",
)
request_duration = meter.create_histogram(
    "app_request_duration_seconds",
    unit="s",
    description="Latencia de solicitudes de las aplicaciones",
)
active_requests = meter.create_up_down_counter(
    "app_active_requests",
    unit="1",
    description="Solicitudes activas en las aplicaciones",
)
db_duration = meter.create_histogram(
    "app_db_duration_seconds",
    unit="s",
    description="Latencia de consultas PostgreSQL en las aplicaciones",
)


class TraceJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        context = trace.get_current_span().get_span_context()
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["service"] = SERVICE_NAME_VALUE
        log_record["environment"] = ENVIRONMENT
        log_record["trace_id"] = format(context.trace_id, "032x") if context.is_valid else None
        log_record["span_id"] = format(context.span_id, "016x") if context.is_valid else None


def configure_logging():
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

if not SDK_DISABLED:
    FastAPIInstrumentor().instrument(tracer_provider=tracer_provider)
    Psycopg2Instrumentor().instrument(tracer_provider=tracer_provider)


def current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service started", extra={"otel_enabled": not SDK_DISABLED})
    yield
    if tracer_provider is not None:
        tracer_provider.shutdown()
    if meter_provider is not None:
        meter_provider.shutdown()
    if logger_provider is not None:
        logger_provider.shutdown()


app = FastAPI(title="OTel Lab - Service B", version=SERVICE_VERSION_VALUE, lifespan=lifespan)
if not SDK_DISABLED:
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME_VALUE}


@app.get("/inventory/{product_id}")
async def read_inventory(product_id: str):
    started = time.perf_counter()
    active_requests.add(1)
    status_code = "200"
    try:
        with tracer.start_as_current_span(
            "inventory.business.validate",
            attributes={"product.id": product_id},
        ) as span:
            if product_id == "missing":
                span.set_status(Status(StatusCode.ERROR, "product not found"))
                status_code = "404"
                raise HTTPException(status_code=404, detail="Product not found")

        with tracer.start_as_current_span(
            "inventory.db.fetch",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system": "postgresql",
                "db.operation.name": "SELECT",
                "product.id": product_id,
            },
        ) as span:
            db_started = time.perf_counter()
            try:
                with psycopg2.connect(DATABASE_URL) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT product_id, available, warehouse, updated_at "
                            "FROM inventory WHERE product_id = %s",
                            (product_id,),
                        )
                        row = cursor.fetchone()
                db_duration.record(time.perf_counter() - db_started, {"operation": "select_inventory"})
                if row is None:
                    span.set_status(Status(StatusCode.ERROR, "product not found"))
                    status_code = "404"
                    raise HTTPException(status_code=404, detail="Product not found")
                result = {
                    "product_id": row[0],
                    "available": row[1],
                    "warehouse": row[2],
                    "updated_at": row[3].isoformat(),
                }
                span.set_attribute("inventory.available", result["available"])
                span.set_attribute("inventory.warehouse", result["warehouse"])
                span.set_status(Status(StatusCode.OK))
            except HTTPException:
                raise
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                status_code = "500"
                logger.exception("inventory database failure", extra={"product_id": product_id})
                raise HTTPException(status_code=500, detail="Inventory database error") from exc

        logger.info(
            "inventory returned",
            extra={"product_id": product_id, "available": result["available"]},
        )
        return {**result, "trace_id": current_trace_id()}
    except HTTPException:
        raise
    finally:
        labels = {"http.method": "GET", "http.route": "/inventory/{product_id}", "http.status_code": status_code}
        requests_total.add(1, labels)
        request_duration.record(time.perf_counter() - started, labels)
        active_requests.add(-1)


@app.post("/inventory/{product_id}/reserve")
async def reserve_inventory(product_id: str, quantity: int = 1):
    with tracer.start_as_current_span(
        "inventory.business.reserve",
        attributes={"product.id": product_id, "reservation.quantity": quantity},
    ) as span:
        logger.info("inventory reservation requested", extra={"product_id": product_id, "quantity": quantity})
        if quantity <= 0:
            span.set_status(Status(StatusCode.ERROR, "invalid quantity"))
            raise HTTPException(status_code=400, detail="quantity must be positive")
        span.set_attribute("reservation.approved", True)
        span.set_status(Status(StatusCode.OK))
        return {"product_id": product_id, "reserved": quantity, "status": "confirmed", "trace_id": current_trace_id()}
