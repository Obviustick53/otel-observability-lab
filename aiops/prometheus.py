"""Read-only Prometheus collection for the local AIOps correlator.

The collector intentionally uses the existing recording rules from the local
Prometheus instance. It never changes Prometheus configuration and never
falls back to historical or synthetic values when live data is unavailable.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from aiops.correlator import CorrelationConfig, MetricSample, _utc


class PrometheusError(RuntimeError):
    """A query failed or returned an unusable Prometheus response."""


@dataclass(frozen=True)
class MetricPoint:
    timestamp: float
    value: float
    service: str


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _epoch(value: str) -> float:
    try:
        return _utc(value).timestamp()
    except ValueError as exc:
        raise ValueError(f"evaluation time must be ISO-8601: {value!r}") from exc


class PrometheusClient:
    """Small standard-library client for the Prometheus HTTP API."""

    def __init__(self, base_url: str = "http://localhost:9090", timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        query = urlencode({key: value for key, value in params.items() if value is not None})
        request = Request(f"{self.base_url}{path}?{query}", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - URL is an explicit CLI input.
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise PrometheusError(f"Prometheus request failed: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("status") != "success":
            error = payload.get("error", "invalid response") if isinstance(payload, dict) else "invalid response"
            raise PrometheusError(f"Prometheus returned an error: {error}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise PrometheusError("Prometheus response has no data object")
        return data

    def query(self, expression: str, evaluation_time: float | None = None) -> list[dict[str, Any]]:
        data = self._get("/api/v1/query", {"query": expression, "time": evaluation_time})
        result = data.get("result")
        if not isinstance(result, list):
            raise PrometheusError("Prometheus instant query result is not a list")
        return [item for item in result if isinstance(item, dict)]

    def query_range(self, expression: str, start: float, end: float, step: int) -> list[dict[str, Any]]:
        data = self._get(
            "/api/v1/query_range",
            {"query": expression, "start": start, "end": end, "step": step},
        )
        result = data.get("result")
        if not isinstance(result, list):
            raise PrometheusError("Prometheus range query result is not a list")
        return [item for item in result if isinstance(item, dict)]

    def server_time(self) -> float:
        data = self._get("/api/v1/query", {"query": "time()"})
        result = data.get("result")
        if not isinstance(result, list) or len(result) != 2:
            raise PrometheusError("Prometheus time() returned no scalar sample")
        parsed = _parse_number(result[1])
        if parsed is None:
            raise PrometheusError("Prometheus time() returned a non-finite timestamp")
        return parsed


def _instant_points(results: Iterable[Mapping[str, Any]]) -> dict[str, MetricPoint]:
    points: dict[str, MetricPoint] = {}
    for result in results:
        metric = result.get("metric")
        value = result.get("value")
        if not isinstance(metric, Mapping) or not isinstance(value, list) or len(value) != 2:
            continue
        service = metric.get("service_name")
        parsed = _parse_number(value[1])
        timestamp = _parse_number(value[0])
        if not isinstance(service, str) or not service or parsed is None or timestamp is None:
            continue
        points[service] = MetricPoint(timestamp=timestamp, value=parsed, service=service)
    return points


def _range_points(results: Iterable[Mapping[str, Any]]) -> dict[str, list[MetricPoint]]:
    points: dict[str, list[MetricPoint]] = {}
    for result in results:
        metric = result.get("metric")
        values = result.get("values")
        if not isinstance(metric, Mapping) or not isinstance(values, list):
            continue
        service = metric.get("service_name")
        if not isinstance(service, str) or not service:
            continue
        service_points = points.setdefault(service, [])
        for value in values:
            if not isinstance(value, list) or len(value) != 2:
                continue
            timestamp = _parse_number(value[0])
            parsed = _parse_number(value[1])
            if timestamp is not None and parsed is not None:
                service_points.append(MetricPoint(timestamp=timestamp, value=parsed, service=service))
    for service in points:
        points[service].sort(key=lambda point: point.timestamp)
    return points


def _stats(points: Iterable[MetricPoint]) -> tuple[float, float, int]:
    values = [point.value for point in points]
    if not values:
        raise PrometheusError("baseline query returned no finite error-rate samples")
    return statistics.fmean(values), statistics.pstdev(values), len(values)


def _selector() -> str:
    # These labels are present in the local Collector output. Keeping the
    # selector explicit avoids the duplicate recording series without the
    # telemetry_scope label observed in the repository's running instance.
    return '{deployment_environment="local",telemetry_scope="local"}'


ERROR_QUERY = f"max by (service_name, deployment_environment, telemetry_scope) (otel:error_rate_5m{_selector()})"
P99_QUERY = f"max by (service_name, deployment_environment, telemetry_scope) (otel:p99_seconds_5m{_selector()})"


def _filter_services(values: Mapping[str, Any], services: set[str] | None) -> dict[str, Any]:
    if not services:
        return dict(values)
    return {service: value for service, value in values.items() if service in services}


def _nearest(points: Iterable[MetricPoint], timestamp: float, tolerance: float) -> MetricPoint | None:
    candidates = [point for point in points if abs(point.timestamp - timestamp) <= tolerance]
    return min(candidates, key=lambda point: abs(point.timestamp - timestamp), default=None)


def compare_live_series(
    error_points: Mapping[str, list[MetricPoint]],
    latency_points: Mapping[str, list[MetricPoint]],
    baselines: Mapping[str, tuple[float, float, int]],
    config: CorrelationConfig,
    tolerance_seconds: float,
) -> dict[str, Any]:
    """Count observed rule evaluations without inventing incident ground truth."""

    comparisons: dict[str, Any] = {}
    for service in sorted(set(error_points) | set(latency_points)):
        baseline = baselines.get(service)
        if baseline is None:
            comparisons[service] = {
                "status": "NO_BASELINE",
                "observations": 0,
                "dynamic_alert_points": 0,
                "static_alert_points": 0,
                "false_positives": None,
                "incidents_detected": None,
                "mean_ttd_seconds": None,
                "limitation": "No frozen baseline was available for this service.",
            }
            continue
        mean, sigma, sample_count = baseline
        pairs: list[tuple[MetricPoint, MetricPoint]] = []
        for error in error_points.get(service, []):
            latency = _nearest(latency_points.get(service, []), error.timestamp, tolerance_seconds)
            if latency is not None:
                pairs.append((error, latency))
        dynamic = [error.value > mean + config.sigma_multiplier * sigma and latency.value * 1000 > config.static_latency_p99_ms_threshold for error, latency in pairs]
        static = [error.value > config.static_error_rate_threshold and latency.value * 1000 > config.static_latency_p99_ms_threshold for error, latency in pairs]

        def transitions(values: list[bool]) -> int:
            return sum(current and not previous for previous, current in zip([False] + values, values))

        comparisons[service] = {
            "status": "VERIFICADO" if pairs else "PARCIAL",
            "observations": len(pairs),
            "dynamic_alert_points": sum(dynamic),
            "static_alert_points": sum(static),
            "dynamic_alert_transitions": transitions(dynamic),
            "static_alert_transitions": transitions(static),
            "frozen_baseline": {"mean": mean, "sigma": sigma, "sample_count": sample_count},
            "false_positives": None,
            "incidents_detected": None,
            "mean_ttd_seconds": None,
            "limitation": "No incident ground truth or incident-start timestamp is available from Prometheus alone; false positives and TTD remain unknown.",
        }
    return comparisons


def collect_live_samples(
    client: PrometheusClient,
    *,
    evaluation_end: float | None = None,
    evaluation_window_minutes: int = 5,
    baseline_window_minutes: int = 30,
    baseline_exclusion_minutes: int = 5,
    step_seconds: int = 15,
    min_baseline_samples: int = 3,
    slo_latency_p99_ms: float = 500.0,
    static_error_rate_threshold: float = 0.05,
    services: set[str] | None = None,
) -> dict[str, Any]:
    """Collect real local metrics with a baseline that cannot learn the window."""

    if evaluation_window_minutes <= 0 or baseline_window_minutes <= 0:
        raise ValueError("evaluation and baseline windows must be positive")
    if baseline_exclusion_minutes < 0 or step_seconds <= 0 or min_baseline_samples <= 0:
        raise ValueError("baseline exclusion, step and minimum sample count are invalid")
    end = evaluation_end if evaluation_end is not None else client.server_time()
    evaluation_start = end - evaluation_window_minutes * 60
    baseline_end = evaluation_start - baseline_exclusion_minutes * 60
    baseline_start = baseline_end - baseline_window_minutes * 60

    current_error = _filter_services(_instant_points(client.query(ERROR_QUERY, end)), services)
    current_p99 = _filter_services(_instant_points(client.query(P99_QUERY, end)), services)
    baseline_points = _filter_services(
        _range_points(client.query_range(ERROR_QUERY, baseline_start, baseline_end, step_seconds)),
        services,
    )
    evaluation_errors = _filter_services(
        _range_points(client.query_range(ERROR_QUERY, evaluation_start, end, step_seconds)),
        services,
    )
    evaluation_p99 = _filter_services(
        _range_points(client.query_range(P99_QUERY, evaluation_start, end, step_seconds)),
        services,
    )

    baselines: dict[str, tuple[float, float, int]] = {}
    baseline_limitations: dict[str, str] = {}
    for service, points in baseline_points.items():
        try:
            mean, sigma, count = _stats(points)
        except PrometheusError as exc:
            baseline_limitations[service] = str(exc)
            continue
        if count < min_baseline_samples:
            baseline_limitations[service] = f"Only {count} finite baseline samples; {min_baseline_samples} required."
            continue
        baselines[service] = (mean, sigma, count)

    samples: list[MetricSample] = []
    limitations: list[str] = []
    candidate_services = sorted(set(current_error) | set(current_p99) | set(baselines))
    for service in candidate_services:
        if service not in current_error or service not in current_p99:
            limitations.append(f"{service}: current error_rate or p99 is missing/non-finite; no incident event emitted.")
            continue
        if service not in baselines:
            limitations.append(f"{service}: frozen baseline unavailable; no incident event emitted.")
            continue
        mean, sigma, count = baselines[service]
        observed_at = max(current_error[service].timestamp, current_p99[service].timestamp)
        samples.append(
            MetricSample.from_mapping(
                {
                    "service": service,
                    "environment": "local",
                    "window_start_utc": _iso(evaluation_start),
                    "window_end_utc": _iso(end),
                    "timestamp_utc": _iso(observed_at),
                    "error_rate": current_error[service].value,
                    "latency_p99_ms": current_p99[service].value * 1000,
                    "baseline_error_rate": mean,
                    "sigma_error_rate": sigma,
                    "slo_latency_p99_ms": slo_latency_p99_ms,
                    "trace_id": "unknown",
                    "trace_id_resolution": "unknown",
                    "trace_id_limitation": "Prometheus metrics do not carry trace_id; resolve it from logs or exemplars with the diagnostic query.",
                    "diagnostic_query": f'Loki/trace backend query for service={service}, window={_iso(evaluation_start)}/{_iso(end)}, status_code=5xx',
                    "evidence_class": "live_local_prometheus",
                    "source_query": ERROR_QUERY,
                    "baseline_window_start_utc": _iso(baseline_start),
                    "baseline_window_end_utc": _iso(baseline_end),
                    "baseline_sample_count": count,
                }
            )
        )

    limitations.extend(f"{service}: {reason}" for service, reason in sorted(baseline_limitations.items()))
    config = CorrelationConfig(
        static_error_rate_threshold=static_error_rate_threshold,
        static_latency_p99_ms_threshold=slo_latency_p99_ms,
    )
    comparisons = compare_live_series(
        evaluation_errors,
        evaluation_p99,
        baselines,
        config,
        tolerance_seconds=max(step_seconds * 1.5, 1.0),
    )
    status = "VERIFICADO" if samples and not limitations else "PARCIAL" if samples else "BLOCKED"
    return {
        "status": status,
        "prometheus_url": client.base_url,
        "queries": {"error_rate": ERROR_QUERY, "latency_p99": P99_QUERY},
        "evaluation_window": {"start_utc": _iso(evaluation_start), "end_utc": _iso(end)},
        "baseline_window": {
            "start_utc": _iso(baseline_start),
            "end_utc": _iso(baseline_end),
            "exclusion_seconds": baseline_exclusion_minutes * 60,
            "frozen_before_evaluation": baseline_end <= evaluation_start,
        },
        "samples": samples,
        "comparisons": comparisons,
        "limitations": limitations,
        "evaluation_series_counts": {
            "error_rate_services": len(evaluation_errors),
            "latency_p99_services": len(evaluation_p99),
        },
    }
