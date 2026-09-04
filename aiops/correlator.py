"""Deterministic local AIOps correlation primitives.

The primary API consumes an already aggregated metric window and emits a
JSON-safe incident event. It has no cloud or runtime dependencies. The legacy
``evaluate``/``compare`` API is retained for the original lab fixture while
the typed API provides stricter validation and auditable evidence fields.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
UNKNOWN_TRACE_ID = "unknown"


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    # Some locally generated evidence uses sub-microsecond precision. Python's
    # datetime stores microseconds, so truncate only the excess precision while
    # preserving the timestamp and its timezone.
    match = re.match(r"^(.*\.)(\d+)([+-]\d\d:\d\d)$", normalized)
    if match:
        normalized = f"{match.group(1)}{match.group(2)[:6].ljust(6, '0')}{match.group(3)}"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a timezone: {value!r}")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _trace(value: Any) -> str:
    if value is None or value == "":
        return UNKNOWN_TRACE_ID
    if not isinstance(value, str):
        raise ValueError("trace_id must be a 32-character hexadecimal string or 'unknown'")
    if value == UNKNOWN_TRACE_ID:
        return UNKNOWN_TRACE_ID
    candidate = value.lower()
    if not TRACE_ID_RE.fullmatch(candidate):
        raise ValueError("trace_id must be a 32-character hexadecimal string or 'unknown'")
    return candidate


@dataclass(frozen=True)
class MetricSample:
    """One immutable evaluation window; rates are ratios and latency is ms."""

    service: str
    environment: str
    window_start_utc: str
    window_end_utc: str
    timestamp_utc: str
    error_rate: float
    latency_p99_ms: float
    baseline_error_rate: float
    sigma_error_rate: float
    slo_latency_p99_ms: float
    trace_id: str = UNKNOWN_TRACE_ID
    trace_id_resolution: str = "unknown"
    trace_id_limitation: str = "No diagnostic trace was provided for this window."
    diagnostic_query: str | None = None
    evidence_class: str = "unspecified"
    source_query: str | None = None
    baseline_window_start_utc: str | None = None
    baseline_window_end_utc: str | None = None
    baseline_sample_count: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MetricSample":
        required = (
            "service", "environment", "window_start_utc", "window_end_utc",
            "timestamp_utc", "error_rate", "latency_p99_ms",
            "baseline_error_rate", "sigma_error_rate", "slo_latency_p99_ms",
        )
        missing = [field for field in required if field not in value]
        if missing:
            raise ValueError(f"sample missing required fields: {', '.join(missing)}")
        if not isinstance(value["service"], str) or not value["service"].strip():
            raise ValueError("service must be a non-empty string")
        if not isinstance(value["environment"], str) or not value["environment"].strip():
            raise ValueError("environment must be a non-empty string")

        start, end, timestamp = (
            _utc(value["window_start_utc"]),
            _utc(value["window_end_utc"]),
            _utc(value["timestamp_utc"]),
        )
        if end <= start:
            raise ValueError("window_end_utc must be after window_start_utc")
        if not start <= timestamp <= end:
            raise ValueError("timestamp_utc must fall inside the evaluation window")

        error_rate = _number(value["error_rate"], "error_rate")
        baseline = _number(value["baseline_error_rate"], "baseline_error_rate")
        sigma = _number(value["sigma_error_rate"], "sigma_error_rate")
        latency = _number(value["latency_p99_ms"], "latency_p99_ms")
        slo = _number(value["slo_latency_p99_ms"], "slo_latency_p99_ms")
        if not 0 <= error_rate <= 1 or not 0 <= baseline <= 1:
            raise ValueError("error_rate and baseline_error_rate must be between 0 and 1")
        if sigma < 0 or latency < 0 or slo <= 0:
            raise ValueError("sigma/latency must be non-negative and SLO must be positive")

        resolution = value.get("trace_id_resolution", "unknown")
        limitation = value.get("trace_id_limitation", "No diagnostic trace was provided for this window.")
        if not isinstance(resolution, str) or not resolution.strip():
            raise ValueError("trace_id_resolution must be a non-empty string")
        if not isinstance(limitation, str) or not limitation.strip():
            raise ValueError("trace_id_limitation must be a non-empty string")
        evidence_class = value.get("evidence_class", "unspecified")
        if not isinstance(evidence_class, str) or not evidence_class.strip():
            raise ValueError("evidence_class must be a non-empty string")
        source_query = value.get("source_query")
        if source_query is not None and not isinstance(source_query, str):
            raise ValueError("source_query must be a string when provided")

        baseline_start_value = value.get("baseline_window_start_utc")
        baseline_end_value = value.get("baseline_window_end_utc")
        if (baseline_start_value is None) != (baseline_end_value is None):
            raise ValueError("baseline window start and end must be provided together")
        baseline_start = baseline_end = None
        if baseline_start_value is not None and baseline_end_value is not None:
            baseline_start, baseline_end = _utc(baseline_start_value), _utc(baseline_end_value)
            if baseline_end <= baseline_start:
                raise ValueError("baseline_window_end_utc must be after baseline_window_start_utc")
            if baseline_end > start:
                raise ValueError("frozen baseline must end at or before the evaluation window start")
        sample_count = value.get("baseline_sample_count")
        if sample_count is not None:
            if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
                raise ValueError("baseline_sample_count must be a positive integer")
        return cls(
            service=value["service"].strip(), environment=value["environment"].strip(),
            window_start_utc=_iso(start), window_end_utc=_iso(end), timestamp_utc=_iso(timestamp),
            error_rate=error_rate, latency_p99_ms=latency, baseline_error_rate=baseline,
            sigma_error_rate=sigma, slo_latency_p99_ms=slo, trace_id=_trace(value.get("trace_id")),
            trace_id_resolution=resolution.strip(), trace_id_limitation=limitation.strip(),
            diagnostic_query=value.get("diagnostic_query"),
            evidence_class=evidence_class.strip(), source_query=source_query,
            baseline_window_start_utc=_iso(baseline_start) if baseline_start else None,
            baseline_window_end_utc=_iso(baseline_end) if baseline_end else None,
            baseline_sample_count=sample_count,
        )


@dataclass(frozen=True)
class CorrelationConfig:
    sigma_multiplier: float = 2.0
    static_error_rate_threshold: float = 0.05
    static_latency_p99_ms_threshold: float = 400.0

    def __post_init__(self) -> None:
        if self.sigma_multiplier < 0:
            raise ValueError("sigma_multiplier cannot be negative")
        if not 0 <= self.static_error_rate_threshold <= 1:
            raise ValueError("static_error_rate_threshold must be between 0 and 1")
        if self.static_latency_p99_ms_threshold <= 0:
            raise ValueError("static_latency_p99_ms_threshold must be positive")


def _pct(value: float) -> float:
    return round(value * 100, 6)


def _event_id(sample: MetricSample, config: CorrelationConfig, correlated: bool) -> str:
    payload = {"sample": sample.__dict__, "sigma_multiplier": config.sigma_multiplier, "correlated": correlated}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"aiops-{digest[:16]}"


def _severity(sample: MetricSample, correlated: bool, error_breach: bool, latency_breach: bool) -> str:
    if not correlated:
        return "warning" if error_breach or latency_breach else "info"
    return "critical" if sample.error_rate >= 0.5 or sample.latency_p99_ms >= 2 * sample.slo_latency_p99_ms else "high"


def correlate(sample: MetricSample | Mapping[str, Any], config: CorrelationConfig | None = None) -> dict[str, Any]:
    """Evaluate ``error anomaly AND p99 SLO breach`` and return an event."""

    config = config or CorrelationConfig()
    normalized = sample if isinstance(sample, MetricSample) else MetricSample.from_mapping(sample)
    dynamic_threshold = normalized.baseline_error_rate + config.sigma_multiplier * normalized.sigma_error_rate
    error_breach = normalized.error_rate > dynamic_threshold
    latency_breach = normalized.latency_p99_ms > normalized.slo_latency_p99_ms
    correlated = error_breach and latency_breach
    static_error_breach = normalized.error_rate > config.static_error_rate_threshold
    static_latency_breach = normalized.latency_p99_ms > config.static_latency_p99_ms_threshold
    return {
        "schema_version": "aiops.incident.v1",
        "event_id": _event_id(normalized, config, correlated),
        "service": normalized.service,
        "environment": normalized.environment,
        "window": {
            "start_utc": normalized.window_start_utc, "end_utc": normalized.window_end_utc,
            "duration_seconds": round((_utc(normalized.window_end_utc) - _utc(normalized.window_start_utc)).total_seconds(), 6),
        },
        "observed": {"error_rate": normalized.error_rate, "error_rate_pct": _pct(normalized.error_rate), "latency_p99_ms": normalized.latency_p99_ms},
        "baseline": {"error_rate": normalized.baseline_error_rate, "error_rate_pct": _pct(normalized.baseline_error_rate)},
        "sigma": {"error_rate": normalized.sigma_error_rate, "error_rate_pct": _pct(normalized.sigma_error_rate)},
        "baseline_window": {
            "start_utc": normalized.baseline_window_start_utc,
            "end_utc": normalized.baseline_window_end_utc,
            "sample_count": normalized.baseline_sample_count,
            "frozen_before_evaluation": normalized.baseline_window_end_utc is None
            or normalized.baseline_window_end_utc <= normalized.window_start_utc,
        },
        "slo": {"latency_p99_ms": normalized.slo_latency_p99_ms},
        "rule": {
            "expression": "error_rate > baseline_error_rate + 2*sigma_error_rate AND latency_p99_ms > slo_latency_p99_ms",
            "sigma_multiplier": config.sigma_multiplier,
            "baseline_training_window_excluded": True,
        },
        "thresholds": {
            "dynamic_error_rate": round(dynamic_threshold, 9), "dynamic_error_rate_pct": _pct(dynamic_threshold),
            "static": {"error_rate": config.static_error_rate_threshold, "error_rate_pct": _pct(config.static_error_rate_threshold), "latency_p99_ms": config.static_latency_p99_ms_threshold},
        },
        "conditions": {
            "error_rate_above_dynamic": error_breach, "latency_p99_above_slo": latency_breach,
            "correlated_incident": correlated, "static_error_rate_breach": static_error_breach,
            "static_latency_breach": static_latency_breach,
        },
        "severity": _severity(normalized, correlated, error_breach, latency_breach),
        "timestamp": normalized.timestamp_utc,
        "trace_id": normalized.trace_id,
        "trace_id_resolution": normalized.trace_id_resolution,
        "trace_id_limitation": normalized.trace_id_limitation,
        "diagnostic_query": normalized.diagnostic_query,
        "evidence_class": normalized.evidence_class,
        "source_query": normalized.source_query,
    }


def _case_metrics(results: list[dict[str, Any]], rule_name: str) -> dict[str, Any]:
    alerts = [result for result in results if result[rule_name]]
    incidents = [result for result in results if result["incident"]]
    false_positives = [result for result in alerts if not result["incident"]]
    detected = [result for result in alerts if result["incident"]]
    ttd = [result["ttd_seconds"] for result in detected if result["ttd_seconds"] is not None]
    normal_count = len(results) - len(incidents)
    return {
        "alerts": len(alerts), "false_positives": len(false_positives),
        "false_positive_rate_pct": round(len(false_positives) / normal_count * 100, 6) if normal_count else 0.0,
        "incidents_total": len(incidents), "incidents_detected": len(detected),
        "incidents_missed": len(incidents) - len(detected),
        "mean_ttd_seconds": round(sum(ttd) / len(ttd), 6) if ttd else None,
        "max_ttd_seconds": round(max(ttd), 6) if ttd else None,
    }


def compare_rules(cases: Iterable[Mapping[str, Any]], config: CorrelationConfig | None = None) -> dict[str, Any]:
    """Compare dynamic conjunction to an immutable static two-threshold rule."""

    config = config or CorrelationConfig()
    results = []
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("each comparison case needs a non-empty case_id")
        event = correlate(case["sample"], config)
        incident = bool(case.get("incident", False))
        ttd_seconds = None
        if incident and case.get("incident_start_utc") is not None:
            ttd_seconds = (_utc(event["timestamp"]) - _utc(case["incident_start_utc"])).total_seconds()
            if ttd_seconds < 0:
                raise ValueError(f"case {case_id!r} has detection timestamp before incident start")
        results.append({
            "case_id": case_id, "incident": incident,
            "dynamic_alert": event["conditions"]["correlated_incident"],
            "static_alert": event["conditions"]["static_error_rate_breach"] and event["conditions"]["static_latency_breach"],
            "ttd_seconds": ttd_seconds, "event_id": event["event_id"], "severity": event["severity"],
        })
    dynamic, static = _case_metrics(results, "dynamic_alert"), _case_metrics(results, "static_alert")
    static_fp = static["false_positives"]
    return {
        "schema_version": "aiops.rule-comparison.v1",
        "evaluation": {
            "cases": len(results), "ground_truth_is_fixture_metadata": True,
            "baseline_is_not_retrained_during_evaluation": True,
            "static_rule": "error_rate > static_error_rate_threshold AND latency_p99_ms > static_latency_p99_ms_threshold",
            "dynamic_rule": "error_rate > baseline_error_rate + 2*sigma_error_rate AND latency_p99_ms > slo_latency_p99_ms",
            "config": {"sigma_multiplier": config.sigma_multiplier, "static_error_rate_threshold": config.static_error_rate_threshold, "static_latency_p99_ms_threshold": config.static_latency_p99_ms_threshold},
        },
        "dynamic_rule": dynamic, "static_rule": static,
        "noise_comparison": {
            "false_positive_delta_static_minus_dynamic": static_fp - dynamic["false_positives"],
            "false_positive_reduction_pct_vs_static": round((static_fp - dynamic["false_positives"]) / static_fp * 100, 6) if static_fp else 0.0,
            "incident_detection_delta_dynamic_minus_static": dynamic["incidents_detected"] - static["incidents_detected"],
        },
        "cases": results,
    }


# Compatibility with the original three-window fixture in this repository.
def evaluate(window: dict[str, Any]) -> dict[str, Any]:
    error_rate = float(window["observed_error_rate"])
    baseline = float(window["baseline_mean"])
    sigma = float(window["baseline_sigma"])
    p99 = float(window["latency_p99_seconds"])
    slo = float(window["slo_latency_p99_seconds"])
    dynamic_threshold = baseline + 2 * sigma
    dynamic_trigger = error_rate > dynamic_threshold and p99 > slo
    static_threshold = float(window.get("static_error_rate_threshold", 0.05))
    static_trigger = error_rate > static_threshold and p99 > slo
    trace_id = _trace(window.get("trace_id"))
    return {
        "service": window["service"], "environment": window["environment"],
        "window": {"start": window["window_start"], "end": window["window_end"]},
        "observed": {"error_rate": error_rate, "latency_p99_seconds": p99},
        "baseline": {"mean": baseline, "sigma": sigma, "threshold_2sigma": dynamic_threshold},
        "slo": {"latency_p99_seconds": slo},
        "severity": "critical" if dynamic_trigger else "info", "timestamp": window["window_end"],
        "trace_id": trace_id, "trace_resolution": window.get("trace_resolution", "diagnostic query required"),
        "correlation_rule": "error_rate > baseline_mean + 2*sigma AND latency_p99 > SLO",
        "dynamic_trigger": dynamic_trigger,
        "static_comparison": {"threshold": static_threshold, "trigger": static_trigger, "dynamic_and_static_agree": dynamic_trigger == static_trigger},
    }


def compare(windows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate(window) for window in windows]
    dynamic = sum(row["dynamic_trigger"] for row in rows)
    static = sum(row["static_comparison"]["trigger"] for row in rows)
    dynamic_fp = sum(row["dynamic_trigger"] and not original.get("ground_truth_incident", False) for row, original in zip(rows, windows))
    static_fp = sum(row["static_comparison"]["trigger"] and not original.get("ground_truth_incident", False) for row, original in zip(rows, windows))
    return {
        "fixture_type": "synthetic", "windows_evaluated": len(rows),
        "dynamic_rule": {"incidents_detected": dynamic, "false_positives_observed": dynamic_fp},
        "static_rule": {"incidents_detected": static, "false_positives_observed": static_fp},
        "rows": rows,
        "interpretation": "Las métricas y trace_id de este archivo son fixtures sintéticos; deben separarse de evidencia live.",
    }


def main() -> None:
    """Compatibility CLI for the original fixture reproduction command."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Evaluate a local AIOps JSON fixture")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = compare(payload["windows"]) if "windows" in payload else evaluate(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
