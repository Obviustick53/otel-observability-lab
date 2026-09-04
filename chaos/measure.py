"""Measure a bounded chaos run without fabricating an alert or a timestamp.

The runner stores request samples and raw observations from Prometheus and
Alertmanager. This module is deliberately dependency-free so it can be used
offline by the coordinator and by unit tests.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse UTC ISO-8601 timestamps, including PowerShell's 7-digit fraction."""
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if "." in normalized:
        head, tail = normalized.split(".", 1)
        zone = ""
        for marker in ("+", "-"):
            position = tail.find(marker)
            if position > 0:
                zone = tail[position:]
                tail = tail[:position]
                break
        normalized = f"{head}.{tail[:6]}{zone}"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def percentile(values: Iterable[float], q: float) -> float | None:
    """Return the nearest-rank percentile used by the existing lab report."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _phase_records(records: list[dict[str, Any]], phase: str) -> list[dict[str, Any]]:
    """Select a phase; accept ``chaos`` as the runner's injection alias."""
    aliases = {"injection": {"injection", "chaos"}, "baseline": {"baseline"}, "recovery": {"recovery"}}
    if any("phase" in record for record in records):
        return [record for record in records if record.get("phase") in aliases.get(phase, {phase})]
    return records if phase == "injection" else []


def _phase_elapsed_seconds(records: list[dict[str, Any]], phase: str) -> float | None:
    phase_records = _phase_records(records, phase)
    starts = [parse_timestamp(item.get("started_utc")) for item in phase_records]
    ends = [parse_timestamp(item.get("completed_utc")) for item in phase_records]
    starts = [value for value in starts if value]
    ends = [value for value in ends if value]
    if not starts or not ends:
        return None
    return max(0.001, (max(ends) - min(starts)).total_seconds())


def _phase_duration(
    records: list[dict[str, Any]],
    phase: str,
    configured_duration_seconds: float | None,
    phase_summaries: list[dict[str, Any]] | None,
) -> float | None:
    """Prefer observed phase boundaries, including phases stopped early."""
    for summary in phase_summaries or []:
        if summary.get("phase") != phase:
            continue
        started = parse_timestamp(summary.get("started_utc"))
        ended = parse_timestamp(summary.get("ended_utc"))
        if started and ended:
            return max(0.001, (ended - started).total_seconds())
    observed = _phase_elapsed_seconds(records, phase)
    return observed or configured_duration_seconds


def summarize_records(
    records: list[dict[str, Any]], *, phase: str, duration_seconds: float | None
) -> dict[str, Any]:
    """Calculate factual request metrics for one phase."""
    phase_records = _phase_records(records, phase)
    durations = [float(item["duration_seconds"]) for item in phase_records]
    errors = sum(1 for item in phase_records if int(item["status_code"]) >= 500)
    total = len(phase_records)
    error_rate = errors / total if total else None
    effective_duration = float(duration_seconds or 0)
    return {
        "phase": phase,
        "requests": total,
        "errors": errors,
        "error_rate": error_rate,
        "availability": (1 - error_rate) if error_rate is not None else None,
        "latency_p99_seconds": percentile(durations, 0.99),
        "throughput_requests_per_second": total / effective_duration if total and effective_duration else None,
        "duration_seconds": effective_duration or None,
    }


def _population_sigma(values: list[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def baseline_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an immutable baseline from the pre-injection request window."""
    baseline_records = _phase_records(records, "baseline")
    indicators = [1.0 if int(item["status_code"]) >= 500 else 0.0 for item in baseline_records]
    latencies = [float(item["duration_seconds"]) for item in baseline_records]
    if not indicators:
        return {
            "status": "unavailable",
            "requests": 0,
            "error_rate": None,
            "sigma": None,
            "latency_p99_seconds": None,
            "source": "baseline request window",
        }
    error_rate = sum(indicators) / len(indicators)
    return {
        "status": "observed",
        "requests": len(indicators),
        "error_rate": error_rate,
        "sigma": _population_sigma(indicators),
        "latency_p99_seconds": percentile(latencies, 0.99),
        "source": "baseline request window; frozen before injection",
    }


def _backend_snapshots(observations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    snapshots: dict[str, list[dict[str, Any]]] = {"prometheus": [], "alertmanager": []}
    for observation in observations:
        for backend in snapshots:
            snapshot = observation.get(backend)
            if isinstance(snapshot, dict):
                snapshots[backend].append(snapshot)
    return snapshots


def _firing_alerts(
    observations: list[dict[str, Any]], *, injection_started: datetime | None
) -> dict[str, Any]:
    """Extract only API-reported firing alerts and classify their timing."""
    snapshots = _backend_snapshots(observations)
    candidates: list[dict[str, Any]] = []
    backend_status: dict[str, str] = {}
    for backend, entries in snapshots.items():
        if not entries:
            backend_status[backend] = "not_queried"
            continue
        backend_status[backend] = "available" if any(
            entry.get("available") is True for entry in entries
        ) else "unavailable"
        for entry in entries:
            observed_at = parse_timestamp(entry.get("observed_at_utc"))
            for alert in entry.get("alerts", []) or []:
                state = str(alert.get("state", "")).lower()
                status_state = str(alert.get("status_state", "")).lower()
                if state != "firing" and status_state != "firing":
                    continue
                if "actionable" in alert and not alert.get("actionable"):
                    continue
                # Prometheus exposes activeAt, which is not a firing timestamp
                # when an alert has a `for` clause. Alertmanager startsAt is
                # accepted as the firing timestamp; active_at is retained as
                # context only.
                firing_timestamp = parse_timestamp(
                    alert.get("firing_timestamp_utc") or alert.get("starts_at")
                )
                candidates.append(
                    {
                        "source": backend,
                        "alert_name": alert.get("alert_name", "unknown"),
                        "state": "firing",
                        "firing_timestamp_utc": firing_timestamp.isoformat().replace("+00:00", "Z")
                        if firing_timestamp
                        else None,
                        "firing_timestamp_source": alert.get("firing_timestamp_source")
                        or ("alertmanager.startsAt" if backend == "alertmanager" and firing_timestamp else None),
                        "active_at_utc": alert.get("active_at_utc") or alert.get("active_at"),
                        "observed_at_utc": observed_at.isoformat().replace("+00:00", "Z")
                        if observed_at
                        else None,
                        "labels": alert.get("labels", {}),
                        "annotations": alert.get("annotations", {}),
                    }
                )

    if not candidates:
        available_backends = sum(status == "available" for status in backend_status.values())
        unavailable_backends = sum(status == "unavailable" for status in backend_status.values())
        if available_backends and unavailable_backends:
            classification = "PARTIAL_ALERT_BACKEND_UNAVAILABLE"
        elif available_backends:
            classification = "NO_ACTIONABLE_ALERT_FIRED"
        elif unavailable_backends:
            classification = "BACKEND_UNAVAILABLE"
        else:
            classification = "ALERT_BACKEND_NOT_QUERIED"
        return {
            "classification": classification,
            "backend_status": backend_status,
            "firing_alerts": [],
            "first_firing": None,
        }

    timed: list[dict[str, Any]] = []
    preexisting: list[dict[str, Any]] = []
    untimed: list[dict[str, Any]] = []
    for candidate in candidates:
        firing = parse_timestamp(candidate.get("firing_timestamp_utc"))
        if not firing:
            untimed.append(candidate)
        elif injection_started and firing < injection_started:
            preexisting.append(candidate)
        else:
            timed.append(candidate)

    timed.sort(key=lambda item: parse_timestamp(item["firing_timestamp_utc"]) or datetime.max.replace(tzinfo=timezone.utc))
    first = timed[0] if timed else None
    if not injection_started:
        classification = "INJECTION_START_UNAVAILABLE"
        first = None
    elif first:
        classification = "VERIFIED_ALERT_FIRING"
    elif untimed and not preexisting:
        classification = "FIRING_TIMESTAMP_UNAVAILABLE"
    elif preexisting:
        classification = "PREEXISTING_ALERT_NO_NEW_FIRING"
    else:
        classification = "NO_NEW_ALERT_FIRED"
    return {
        "classification": classification,
        "backend_status": backend_status,
        "firing_alerts": candidates,
        "first_firing": first,
        "preexisting_firing_alerts": preexisting,
    }


def build_report(
    records: list[dict[str, Any]],
    metadata: dict[str, Any],
    observations: list[dict[str, Any]],
    baseline_records: list[dict[str, Any]] | None = None,
    recovery_records: list[dict[str, Any]] | None = None,
    phase_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the report consumed by evidence tooling, if the coordinator runs it."""
    injection_duration = _float_or_none(metadata.get("load_duration_seconds"))
    baseline_duration = _float_or_none(metadata.get("baseline_duration_seconds"))
    recovery_duration = _float_or_none(metadata.get("recovery_duration_seconds"))
    baseline_source = baseline_records if baseline_records is not None else records
    baseline = baseline_from_records(baseline_source)
    baseline_duration_observed = _phase_duration(
        baseline_source, "baseline", baseline_duration, phase_summaries
    )
    injection_duration_observed = _phase_duration(
        records, "injection", injection_duration, phase_summaries
    )
    recovery_source = recovery_records if recovery_records is not None else records
    recovery_duration_observed = _phase_duration(
        recovery_source, "recovery", recovery_duration, phase_summaries
    )
    injection = summarize_records(
        records, phase="injection", duration_seconds=injection_duration_observed
    )
    recovery = summarize_records(
        recovery_source,
        phase="recovery",
        duration_seconds=recovery_duration_observed,
    )

    slo = _float_or_none(metadata.get("slo_latency_p99_seconds"))
    error_budget = _float_or_none(metadata.get("slo_error_rate_budget"))
    dynamic_threshold = None
    local_correlated = None
    if baseline["error_rate"] is not None and baseline["sigma"] is not None:
        dynamic_threshold = baseline["error_rate"] + 2 * baseline["sigma"]
        local_correlated = bool(
            injection["error_rate"] is not None
            and injection["latency_p99_seconds"] is not None
            and slo is not None
            and injection["error_rate"] > dynamic_threshold
            and injection["latency_p99_seconds"] > slo
        )

    injection_started = parse_timestamp(metadata.get("injection_started_utc"))
    alert_result = _firing_alerts(observations, injection_started=injection_started)
    first_firing = alert_result.get("first_firing")
    firing_timestamp = parse_timestamp(first_firing.get("firing_timestamp_utc")) if first_firing else None
    mttd_seconds = (
        (firing_timestamp - injection_started).total_seconds()
        if firing_timestamp and injection_started
        else None
    )
    first_alert_observed = parse_timestamp(first_firing.get("observed_at_utc")) if first_firing else None
    observed_mttd_seconds = (
        (first_alert_observed - injection_started).total_seconds()
        if first_alert_observed and injection_started
        else None
    )
    error_budget_consumed = (
        injection["error_rate"] / error_budget
        if injection["error_rate"] is not None and error_budget and error_budget > 0
        else None
    )
    trace_ids = [
        item.get("trace_id")
        for item in _phase_records(records, "injection")
        if item.get("trace_id") and item.get("trace_id") != "unknown"
    ]

    rollback_verified = bool(metadata.get("rollback_verified", False))
    recovery_error_rate = recovery.get("error_rate")
    recovery_min_availability = _float_or_none(
        metadata.get("recovery_min_availability", 1 - (error_budget or 0))
    )
    recovery_healthy = recovery["requests"] > 0 and (
        recovery_error_rate is not None
        and recovery["availability"] is not None
        and recovery["availability"] >= (recovery_min_availability or 0)
    )
    recovery_verified = rollback_verified and recovery_healthy

    limitations = [
        "p99 and request rates are calculated from bounded HTTP samples; they are not substituted for backend metrics.",
        "No alert is inferred from an HTTP error or from the local correlator; MTTD requires an API-reported firing timestamp.",
        "The baseline is frozen from the pre-injection phase and is not learned during the chaos window.",
    ]
    if alert_result["classification"] != "VERIFIED_ALERT_FIRING":
        limitations.append(
            "The result is not a verified alert firing unless Prometheus or Alertmanager reported a target alert in firing state."
        )
    if alert_result["classification"] == "PARTIAL_ALERT_BACKEND_UNAVAILABLE":
        limitations.append("Only one alert backend was available; the unavailable backend was not treated as a negative alert result.")
    if not trace_ids:
        limitations.append("No response trace_id was observed; resolve correlation from logs or exemplars after the run.")
    if not rollback_verified:
        limitations.append("Rollback was not verified; recovery cannot be claimed even if the recovery sample looks healthy.")
    if rollback_verified and not recovery_healthy:
        limitations.append("Rollback control was verified, but the recovery window did not meet its availability/error-rate acceptance.")

    started = bool(metadata.get("injection_started_utc"))
    if not started:
        execution_classification = "NOT_EXECUTED"
    elif not rollback_verified:
        execution_classification = "EXECUTED_ROLLBACK_UNVERIFIED"
    elif not recovery_verified:
        execution_classification = "EXECUTED_RECOVERY_UNVERIFIED"
    else:
        execution_classification = "EXECUTED_RECOVERED"

    return {
        "experiment": metadata.get("experiment"),
        "environment": metadata.get("environment", "local"),
        "telemetry_scope": metadata.get("telemetry_scope", "local-executed"),
        "status": "executed" if started else "not_executed",
        "execution_classification": execution_classification,
        "injection": {
            "control": metadata.get("chaos_parameter"),
            "control_name": metadata.get("injection_control"),
            "control_requested_value": metadata.get("injection_control_value"),
            "control_observed_value": metadata.get("injection_control_observed_value"),
            "requested_at_utc": metadata.get("injection_requested_utc"),
            "started_at_utc": metadata.get("injection_started_utc"),
            "start_source": metadata.get("injection_start_source"),
            "ended_at_utc": metadata.get("injection_ended_utc"),
        },
        "baseline": {
            **baseline,
            "duration_seconds": baseline_duration_observed,
            "configured_duration_seconds": baseline_duration,
        },
        "injection_metrics": injection,
        "recovery_metrics": recovery,
        "slo": {
            "latency_p99_seconds": slo,
            "error_rate_budget": error_budget,
            "latency_breached": bool(
                injection["latency_p99_seconds"] is not None
                and slo is not None
                and injection["latency_p99_seconds"] > slo
            ),
            "error_budget_consumed_ratio": error_budget_consumed,
            "error_budget_remaining_ratio": max(0.0, 1 - error_budget_consumed)
            if error_budget_consumed is not None
            else None,
        },
        "local_correlation": {
            "rule": "error_rate > baseline_error_rate + 2*sigma AND latency_p99 > SLO",
            "dynamic_error_rate_threshold": dynamic_threshold,
            "correlated": local_correlated,
            "note": "This is a sample calculation, not an invented backend alert.",
        },
        "alert_observation": alert_result,
        "firing_timestamp_utc": first_firing.get("firing_timestamp_utc") if first_firing else None,
        "mttd_seconds": mttd_seconds,
        "mttd_under_120_seconds": mttd_seconds is not None and mttd_seconds < 120,
        "alert_observed_at_utc": first_firing.get("observed_at_utc") if first_firing else None,
        "observed_mttd_seconds_upper_bound": observed_mttd_seconds,
        "mttd_timestamp_basis": first_firing.get("firing_timestamp_source") if first_firing else None,
        "trace_ids_observed": trace_ids[:20],
        "trace_limitations": "Response trace_id is retained when present; otherwise use logs/exemplars.",
        "stop_conditions": {
            "configured": metadata.get("stop_conditions", []),
            "triggered": metadata.get("stop_condition_triggered"),
        },
        "rollback": {
            "requested_at_utc": metadata.get("rollback_requested_utc"),
            "completed_at_utc": metadata.get("rollback_completed_utc"),
            "verified": bool(metadata.get("rollback_verified", False)),
            "actions": metadata.get("rollback_actions", []),
            "control_after_rollback": metadata.get("rollback_control_value"),
            "recovery_window_seconds": recovery_duration_observed,
            "recovery_acceptance": {
                "minimum_availability": recovery_min_availability,
                "observed_availability": recovery["availability"],
                "observed_error_rate": recovery_error_rate,
                "healthy": recovery_healthy,
                "verified": recovery_verified,
            },
        },
        "measured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "limitations": limitations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--alerts", type=Path)
    parser.add_argument("--baseline-records", type=Path)
    parser.add_argument("--recovery-records", type=Path)
    parser.add_argument("--phases", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = json.loads(args.records.read_text(encoding="utf-8"))
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    observations = []
    if args.alerts and args.alerts.exists():
        observations = json.loads(args.alerts.read_text(encoding="utf-8"))
    baseline_records = (
        json.loads(args.baseline_records.read_text(encoding="utf-8"))
        if args.baseline_records and args.baseline_records.exists()
        else None
    )
    recovery_records = (
        json.loads(args.recovery_records.read_text(encoding="utf-8"))
        if args.recovery_records and args.recovery_records.exists()
        else None
    )
    phase_summaries = (
        json.loads(args.phases.read_text(encoding="utf-8"))
        if args.phases and args.phases.exists()
        else None
    )
    report = build_report(
        records,
        metadata,
        observations,
        baseline_records,
        recovery_records,
        phase_summaries,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
