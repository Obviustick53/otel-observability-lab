"""Run the local AIOps correlator against a fixture, history, or Prometheus.

The default is ``live``. Live collection is read-only and has no historical
fallback: if Prometheus cannot provide finite current metrics and a frozen
baseline, the output is BLOCKED/PARCIAL and says why.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aiops.correlator import CorrelationConfig, MetricSample, compare_rules, correlate  # noqa: E402
from aiops.prometheus import (  # noqa: E402
    ERROR_QUERY,
    P99_QUERY,
    PrometheusClient,
    PrometheusError,
    _epoch,
    collect_live_samples,
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _request_error(request: dict[str, Any]) -> float:
    status = request.get("http_status_code", request.get("status"))
    if isinstance(status, int):
        return 1.0 if status >= 500 else 0.0
    return 1.0 if request.get("outcome") in {"error", "http_error", "failure"} else 0.0


def _population_sigma(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def build_historical_sample(
    chaos: dict[str, Any],
    baseline: dict[str, Any],
    trace_summary: dict[str, Any],
    trace_detail: dict[str, Any] | None,
    slo_latency_p99_ms: float,
) -> MetricSample:
    """Reprocess old local artifacts only when the caller explicitly asks."""

    chaos_window = chaos["experiment_window"]
    chaos_metrics = chaos["metrics"]
    baseline_window = baseline["experiment_window"]
    baseline_requests = baseline.get("requests", [])
    if not baseline_requests:
        raise ValueError("historical baseline must contain request samples to derive sigma")
    error_indicators = [_request_error(request) for request in baseline_requests]
    trace_id = trace_summary.get("trace_id", "unknown")
    diagnostic_query = trace_detail.get("query") if trace_detail else None
    resolved = trace_id != "unknown"
    return MetricSample.from_mapping(
        {
            "service": "service-a",
            "environment": "local-historical",
            "window_start_utc": chaos_window["started_utc"],
            "window_end_utc": chaos_window["ended_utc"],
            "timestamp_utc": chaos_window["ended_utc"],
            "error_rate": float(chaos_metrics["error_rate_pct"]) / 100,
            "latency_p99_ms": float(chaos_metrics["latency_p99_ms"]),
            "baseline_error_rate": sum(error_indicators) / len(error_indicators),
            "sigma_error_rate": _population_sigma(error_indicators),
            "slo_latency_p99_ms": slo_latency_p99_ms,
            "trace_id": trace_id,
            "trace_id_resolution": "historical_local_diagnostic_artifact" if resolved else "unknown",
            "trace_id_limitation": "Trace resolved from historical local artifacts; this is not a live query." if resolved else "No trace ID was present in historical diagnostic artifacts.",
            "diagnostic_query": diagnostic_query,
            "evidence_class": "historical_local_evidence_reprocessed",
            "baseline_window_start_utc": baseline_window["started_utc"],
            "baseline_window_end_utc": baseline_window["ended_utc"],
            "baseline_sample_count": len(baseline_requests),
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("live", "historical", "synthetic"), default="live")
    parser.add_argument("--prometheus-url", default="http://localhost:9090")
    parser.add_argument("--evaluation-time", help="Optional fixed ISO-8601 evaluation time for a reproducible Prometheus query")
    parser.add_argument("--evaluation-window-minutes", type=int, default=5)
    parser.add_argument("--baseline-window-minutes", type=int, default=30)
    parser.add_argument("--baseline-exclusion-minutes", type=int, default=5)
    parser.add_argument("--query-step-seconds", type=int, default=15)
    parser.add_argument("--min-baseline-samples", type=int, default=3)
    parser.add_argument("--services", help="Comma-separated service allow-list; default is all local services")
    parser.add_argument("--slo-latency-p99-ms", type=float, default=500.0)
    parser.add_argument("--static-error-rate-threshold", type=float, default=0.05)
    parser.add_argument("--synthetic-fixture", type=Path, default=REPO_ROOT / "tests" / "aiops" / "fixtures" / "synthetic_cases.json")
    parser.add_argument("--real-chaos", type=Path, default=REPO_ROOT / "evidence" / "chaos" / "chaos-final.json")
    parser.add_argument("--real-baseline", type=Path, default=REPO_ROOT / "evidence" / "chaos" / "baseline-final.json")
    parser.add_argument("--real-trace", type=Path, default=REPO_ROOT / "evidence" / "chaos" / "jaeger-error-trace-summary.json")
    parser.add_argument("--real-trace-detail", type=Path, default=REPO_ROOT / "evidence" / "chaos" / "loki-trace-92e1653aff0013f0b1fe25bcc8e5103a.json")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "screenshoot" / "integrator_project" / "02_aiops")
    parser.add_argument("--run-timestamp", default=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    return parser.parse_args()


def fixture_outputs(fixture: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if fixture.get("fixture_kind") != "synthetic":
        raise ValueError("synthetic fixture must declare fixture_kind=synthetic")
    static = fixture["static_thresholds"]
    config = CorrelationConfig(
        sigma_multiplier=2.0,
        static_error_rate_threshold=float(static["error_rate"]),
        static_latency_p99_ms_threshold=float(static["latency_p99_ms"]),
    )
    return [correlate(case["sample"], config) for case in fixture["cases"]], compare_rules(fixture["cases"], config)


def main() -> int:
    args = parse_args()
    fixture = load_json(args.synthetic_fixture)
    synthetic_events, synthetic_comparison = fixture_outputs(fixture)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_json(args.output_dir / "synthetic-correlation-events.json", {
        "evidence_class": "synthetic_fixture",
        "fixture_path": display_path(args.synthetic_fixture),
        "events": synthetic_events,
    })
    write_json(args.output_dir / "synthetic-rule-comparison.json", {
        "evidence_class": "synthetic_fixture",
        "fixture_path": display_path(args.synthetic_fixture),
        "result": synthetic_comparison,
    })

    selected_status = "NOT_REQUESTED"
    selected_limitations: list[str] = []
    selected_files: list[str] = []
    selected_summary: dict[str, Any] = {}

    if args.mode == "synthetic":
        selected_status = "VERIFICADO"
        selected_summary = {"events": len(synthetic_events), "comparison": synthetic_comparison}
    elif args.mode == "historical":
        chaos = load_json(args.real_chaos)
        baseline = load_json(args.real_baseline)
        trace_summary = load_json(args.real_trace)
        trace_detail = load_json(args.real_trace_detail) if args.real_trace_detail.exists() else None
        sample = build_historical_sample(chaos, baseline, trace_summary, trace_detail, args.slo_latency_p99_ms)
        event = correlate(sample, CorrelationConfig(static_error_rate_threshold=args.static_error_rate_threshold, static_latency_p99_ms_threshold=args.slo_latency_p99_ms))
        write_json(args.output_dir / "historical-local-correlation-event.json", {
            "evidence_class": "historical_local_evidence_reprocessed",
            "execution_status": "historical_source_reprocessed_locally; no live backend queried",
            "source_artifacts": [display_path(args.real_chaos), display_path(args.real_baseline), display_path(args.real_trace), display_path(args.real_trace_detail) if trace_detail else None],
            "event": event,
        })
        selected_files.append("historical-local-correlation-event.json")
        selected_status = "PARCIAL"
        selected_limitations = ["Historical artifacts are not live Prometheus observations and do not establish current system state."]
        selected_summary = {"correlated": event["conditions"]["correlated_incident"], "trace_id": event["trace_id"]}
    else:
        services = {value.strip() for value in args.services.split(",") if value.strip()} if args.services else None
        evaluation_end = _epoch(args.evaluation_time) if args.evaluation_time else None
        client = PrometheusClient(args.prometheus_url)
        try:
            collection = collect_live_samples(
                client,
                evaluation_end=evaluation_end,
                evaluation_window_minutes=args.evaluation_window_minutes,
                baseline_window_minutes=args.baseline_window_minutes,
                baseline_exclusion_minutes=args.baseline_exclusion_minutes,
                step_seconds=args.query_step_seconds,
                min_baseline_samples=args.min_baseline_samples,
                slo_latency_p99_ms=args.slo_latency_p99_ms,
                static_error_rate_threshold=args.static_error_rate_threshold,
                services=services,
            )
        except (PrometheusError, ValueError) as exc:
            collection = {
                "status": "BLOCKED",
                "prometheus_url": client.base_url,
                "queries": {"error_rate": ERROR_QUERY, "latency_p99": P99_QUERY},
                "samples": [],
                "comparisons": {},
                "limitations": [str(exc)],
            }
        live_events = [correlate(sample) for sample in collection["samples"]]
        write_json(args.output_dir / "live-prometheus-correlation-events.json", {
            "evidence_class": "live_local_prometheus",
            "execution_status": "live_prometheus_queried" if collection["status"] != "BLOCKED" else "BLOCKED",
            "collection": {key: value for key, value in collection.items() if key != "samples"},
            "events": live_events,
        })
        write_json(args.output_dir / "live-prometheus-rule-comparison.json", {
            "evidence_class": "live_local_prometheus",
            "status": collection["status"],
            "rule": "error_rate > frozen baseline + 2*sigma AND latency_p99 > SLO",
            "comparison": collection["comparisons"],
            "limitation": "Prometheus provides observed rule evaluations but no incident ground truth; false positives and TTD are null unless an incident record is supplied.",
        })
        selected_files.extend(["live-prometheus-correlation-events.json", "live-prometheus-rule-comparison.json"])
        selected_status = collection["status"]
        selected_limitations = collection["limitations"]
        selected_summary = {
            "events": len(live_events),
            "correlated_events": sum(event["conditions"]["correlated_incident"] for event in live_events),
            "services": [event["service"] for event in live_events],
        }

    write_json(args.output_dir / "run-manifest.json", {
        "evidence_class": "local-aiops-run",
        "generated_at_utc": args.run_timestamp,
        "mode": args.mode,
        "command_contract": "python scripts/aiops/run_aiops.py --mode live --prometheus-url http://localhost:9090",
        "aws_execution": "NOT_EXECUTED",
        "synthetic_fixture": display_path(args.synthetic_fixture),
        "selected_status": selected_status,
        "selected_summary": selected_summary,
        "selected_outputs": selected_files,
        "limitations": selected_limitations + ["The synthetic fixture is always emitted separately and is never treated as live evidence."],
    })

    specs = [
        {
            "file": "synthetic-correlation-events.json",
            "rubric_criterion": "AIOps event contract",
            "evidence_type": "synthetic_fixture_result",
            "environment": "local-synthetic",
            "status": "VERIFICADO",
            "observed": f"{len(synthetic_events)} deterministic fixture events evaluated; trace IDs remain explicit fixture values.",
            "limitations": ["Synthetic data is not a production, Prometheus, or AWS observation."],
        },
        {
            "file": "synthetic-rule-comparison.json",
            "rubric_criterion": "Dynamic vs static thresholds and noise",
            "evidence_type": "synthetic_quantitative_comparison",
            "environment": "local-synthetic",
            "status": "VERIFICADO",
            "observed": "Comparison includes alerts, false positives, missed incidents and TTD using fixture ground truth.",
            "limitations": ["Ground truth is fixture metadata, not an incident-management record."],
        },
    ]
    if args.mode == "live":
        specs.extend([
            {
                "file": "live-prometheus-correlation-events.json",
                "rubric_criterion": "AIOps against real local Prometheus metrics",
                "evidence_type": "live_local_prometheus_result",
                "environment": "local",
                "status": selected_status,
                "observed": f"{selected_summary.get('events', 0)} event(s) emitted from read-only Prometheus queries.",
                "limitations": selected_limitations or ["Trace resolution is unknown unless logs/exemplars are queried separately."],
            },
            {
                "file": "live-prometheus-rule-comparison.json",
                "rubric_criterion": "Dynamic vs static thresholds on observed series",
                "evidence_type": "live_local_prometheus_comparison",
                "environment": "local",
                "status": selected_status,
                "observed": "Dynamic/static alert points and transitions are counted over the evaluation window; unknown ground truth is null.",
                "limitations": ["Prometheus alone cannot classify false positives or calculate TTD without an incident start."],
            },
        ])
    elif args.mode == "historical":
        specs.append({
            "file": "historical-local-correlation-event.json",
            "rubric_criterion": "Trace correlation from local diagnostic evidence",
            "evidence_type": "historical_local_evidence_reprocessed",
            "environment": "local-historical",
            "status": "PARCIAL",
            "observed": "Historical local artifacts were reprocessed only because --mode historical was explicit.",
            "limitations": selected_limitations,
        })
    specs.append({
        "file": "run-manifest.json",
        "rubric_criterion": "Reproducibility and evidence separation",
        "evidence_type": "execution_manifest",
        "environment": "local",
        "status": "VERIFICADO",
        "observed": "Mode, command contract, AWS NOT_EXECUTED state and source class are recorded.",
        "limitations": ["Live values are time-dependent unless --evaluation-time is fixed and data retention remains available."],
    })
    write_json(args.output_dir / "aiops-evidence-manifest.json", {
        "schema_version": "aiops.evidence-manifest.v2",
        "generated_at_utc": args.run_timestamp,
        "aws_execution": "NOT_EXECUTED",
        "artifacts": [{**spec, "sha256": sha256_file(args.output_dir / spec["file"])} for spec in specs],
    })
    print(json.dumps({"output_dir": str(args.output_dir), "mode": args.mode, "selected_status": selected_status, "selected_summary": selected_summary}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, TypeError, ValueError, PrometheusError) as exc:
        print(f"AIOps run failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
