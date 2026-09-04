#!/usr/bin/env python3
"""Deterministic local network/security event simulator.

This tool intentionally does not read or emit AWS VPC Flow Logs.  Its records
are labelled ``local-simulated`` so local dashboards cannot be mistaken for
cloud evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable


UTC = timezone.utc

FIELDS = [
    "event_id", "timestamp", "environment", "source", "event_type", "service",
    "src_zone", "dst_zone", "direction", "action", "protocol", "src_ip",
    "dst_ip", "src_port", "dst_port", "bytes", "status", "auth_result",
    "finding_type", "cve_id", "severity", "message", "trace_id",
]


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_start(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def event(event_no: int, timestamp: datetime, event_type: str, **values: Any) -> dict[str, Any]:
    record = {field: None for field in FIELDS}
    record.update(
        event_id=f"security-sim-{event_no:04d}",
        timestamp=iso_utc(timestamp),
        environment="local-simulated",
        source="network-security-simulator",
        event_type=event_type,
        service="platform",
        bytes=0,
        message="synthetic event",
        trace_id="unknown",
    )
    record.update(values)
    return record


def generate_events(start: datetime, seed: int) -> list[dict[str, Any]]:
    """Build a stable, representative event set from a seed.

    The timestamps and values are deterministic for a given ``start`` and
    ``seed``.  Randomness only varies low-value details such as byte counts.
    """
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    event_no = 1

    # Authentication failures include a short burst to make a dashboard query
    # visibly useful.  No credentials or real identities are generated.
    for index in range(48):
        moment = start + timedelta(minutes=index * 12 if index < 36 else 520 + index - 36)
        failed = index >= 36
        records.append(event(
            event_no, moment, "auth_failed" if failed else "auth_success",
            service=rng.choice(["service-a", "service-b", "data-service"]),
            src_zone="internet" if failed else "internal",
            dst_zone="application",
            direction="north_south" if failed else "east_west",
            action="deny" if failed else "allow",
            protocol="https",
            src_ip=f"198.51.100.{(index % 20) + 1}" if failed else f"10.0.2.{(index % 20) + 10}",
            dst_ip="10.0.2.20",
            src_port=40000 + index,
            dst_port=443,
            status="401" if failed else "200",
            auth_result="failure" if failed else "success",
            severity="high" if failed and index >= 22 else ("medium" if failed else "info"),
            message="synthetic failed authentication" if failed else "synthetic successful authentication",
        ))
        event_no += 1

    # Allowed flows cover N-S ingress/egress and E-W service-to-service paths.
    flow_paths = [
        ("north_south", "internet", "application", "external-api", "service-a"),
        ("north_south", "application", "internet", "service-b", "external-api"),
        ("east_west", "application", "database", "service-a", "service-b"),
        ("east_west", "application", "database", "service-b", "data-service"),
    ]
    for index in range(64):
        direction, src_zone, dst_zone, source_service, destination = flow_paths[index % len(flow_paths)]
        records.append(event(
            event_no, start + timedelta(minutes=3 + index * 5), "flow",
            service=source_service,
            src_zone=src_zone,
            dst_zone=dst_zone,
            direction=direction,
            action="allow",
            protocol="tcp",
            src_ip=f"10.0.{(index % 3) + 1}.{(index % 200) + 10}" if direction == "east_west" else "10.0.1.10",
            dst_ip="10.0.2.20" if destination == "data-service" else "203.0.113.10",
            src_port=30000 + index,
            dst_port=5432 if destination == "data-service" else (8001 if destination == "service-b" else 443),
            bytes=rng.randint(1200, 95000),
            status="200",
            severity="info",
            message=f"synthetic allowed {direction} flow to {destination}",
        ))
        event_no += 1

    # Denials are separate event types so they can be queried without relying
    # on a vendor-specific Flow Logs field mapping.
    for index in range(16):
        direction = "north_south" if index % 3 else "east_west"
        records.append(event(
            event_no, start + timedelta(minutes=516 + index), "denial",
            service="edge-gateway" if direction == "north_south" else "service-b",
            src_zone="internet" if direction == "north_south" else "application",
            dst_zone="application" if direction == "north_south" else "database",
            direction=direction,
            action="deny",
            protocol="tcp",
            src_ip=f"203.0.113.{(index % 12) + 1}",
            dst_ip="10.0.2.20",
            src_port=45000 + index,
            dst_port=22 if index % 2 else 5432,
            bytes=0,
            status="403",
            severity="high" if index in {3, 4, 5, 6} else "medium",
            message="synthetic policy denial",
        ))
        event_no += 1

    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)


def summary(records: list[dict[str, Any]], start: datetime, seed: int) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for record in records:
        by_type[record["event_type"]] = by_type.get(record["event_type"], 0) + 1
        severity = record.get("severity") or "unspecified"
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "dataset": "network-security-local-simulation",
        "environment": "local-simulated",
        "source": "network-security-simulator",
        "separation_note": "Synthetic network/authentication events only; no AWS VPC Flow Logs, CloudTrail events, Security Hub findings, CVEs, or real credentials were read.",
        "seed": seed,
        "start": iso_utc(start),
        "event_count": len(records),
        "by_event_type": dict(sorted(by_type.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "trace_id_policy": "unknown; simulator does not invent application trace IDs",
        "security_hub_policy": "not-collected; use read-only AWS Security Hub APIs after subscription preflight",
    }


QUERY_NAMES = ["summary", "auth_failures", "north_south", "east_west", "denials", "traffic_anomalies", "findings", "cves"]

ANOMALY_WINDOW_MINUTES = 5
ANOMALY_BASELINE_MINUTES = 30
ANOMALY_BASELINE_GAP_MINUTES = 30
ANOMALY_SIGMA_MULTIPLIER = 2.0


def _bucket_start(value: datetime, origin: datetime, bucket_minutes: int) -> datetime:
    elapsed_seconds = max(0.0, (value - origin).total_seconds())
    bucket_seconds = bucket_minutes * 60
    return origin + timedelta(seconds=int(elapsed_seconds // bucket_seconds) * bucket_seconds)


def detect_traffic_anomalies(
    records: list[dict[str, Any]],
    *,
    window_minutes: int = ANOMALY_WINDOW_MINUTES,
    baseline_minutes: int = ANOMALY_BASELINE_MINUTES,
    baseline_gap_minutes: int = ANOMALY_BASELINE_GAP_MINUTES,
    sigma_multiplier: float = ANOMALY_SIGMA_MULTIPLIER,
) -> dict[str, Any]:
    """Detect traffic spikes without learning from the detection window.

    The baseline ends before a guard gap.  This keeps a preceding chaos burst
    or incident from teaching the detector that the abnormal traffic is normal.
    Counts and bytes are intentionally aggregated to fixed, low-cardinality
    signals; source IPs and trace IDs are not exported as metric labels.
    """
    if not records:
        raise ValueError("event list is empty")
    if min(window_minutes, baseline_minutes, baseline_gap_minutes) <= 0:
        raise ValueError("window, baseline, and gap must be positive")
    if sigma_multiplier < 0:
        raise ValueError("sigma multiplier must be non-negative")

    timestamps = [parse_start(record["timestamp"]) for record in records]
    first = min(timestamps)
    latest = max(timestamps)
    recent_start = latest - timedelta(minutes=window_minutes)
    baseline_end = recent_start - timedelta(minutes=baseline_gap_minutes)
    baseline_start = baseline_end - timedelta(minutes=baseline_minutes)

    signals = {
        "rejected_flows": ("all", "count", lambda row: row.get("event_type") == "denial"),
        "north_south_bytes": ("north_south", "bytes", lambda row: row.get("event_type") == "flow" and row.get("direction") == "north_south"),
        "east_west_bytes": ("east_west", "bytes", lambda row: row.get("event_type") == "flow" and row.get("direction") == "east_west"),
    }
    results: list[dict[str, Any]] = []
    for signal, (direction, value_kind, predicate) in signals.items():
        baseline_buckets: dict[datetime, float] = defaultdict(float)
        current_value = 0.0
        baseline_records = 0
        for record, timestamp in zip(records, timestamps):
            if not predicate(record):
                continue
            value = 1.0 if value_kind == "count" else float(record.get("bytes") or 0)
            if recent_start <= timestamp <= latest:
                current_value += value
            elif baseline_start <= timestamp < baseline_end:
                baseline_bucket = _bucket_start(timestamp, baseline_start, window_minutes)
                baseline_buckets[baseline_bucket] += value
                baseline_records += 1

        bucket_count = max(1, int(baseline_minutes / window_minutes))
        baseline_values = [baseline_buckets.get(baseline_start + timedelta(minutes=index * window_minutes), 0.0) for index in range(bucket_count)]
        baseline_mean = mean(baseline_values)
        baseline_sigma = pstdev(baseline_values)
        threshold = baseline_mean + sigma_multiplier * baseline_sigma
        enough_history = latest - first >= timedelta(minutes=baseline_minutes + baseline_gap_minutes)
        anomaly = bool(enough_history and current_value > threshold and current_value > 0)
        results.append({
            "signal": signal,
            "direction": direction,
            "observed_5m": int(current_value) if value_kind == "count" else current_value,
            "baseline_mean_30m": baseline_mean,
            "baseline_sigma_30m": baseline_sigma,
            "threshold_30m": threshold,
            "z_score": ((current_value - baseline_mean) / baseline_sigma) if baseline_sigma else None,
            "baseline_bucket_count": bucket_count,
            "baseline_records": baseline_records,
            "anomalous": anomaly,
            "status": "DETECTED" if anomaly else ("NORMAL" if enough_history else "INSUFFICIENT_DATA"),
        })

    return {
        "dataset": "network-security-local-simulation",
        "environment": "local-simulated",
        "window": {"start": iso_utc(recent_start), "end": iso_utc(latest)},
        "baseline": {
            "start": iso_utc(baseline_start),
            "end": iso_utc(baseline_end),
            "gap_minutes": baseline_gap_minutes,
            "window_minutes": baseline_minutes,
            "policy": "baseline ends before a guard gap and never includes the detection window",
        },
        "rule": f"observed_5m > baseline_mean_30m + {sigma_multiplier:g}*baseline_sigma_30m and observed_5m > 0",
        "signals": results,
        "security_hub_policy": "not-collected; anomaly detection does not create or represent Security Hub findings",
    }


def load_records(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.exists():
        raise FileNotFoundError(f"event file not found: {events_path}")
    with events_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def query_rows(events_path: Path, query_name: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    records = load_records(events_path)
    if query_name == "summary":
        counts: dict[tuple[str, str], int] = {}
        for record in records:
            key = (record["event_type"], record.get("severity") or "unspecified")
            counts[key] = counts.get(key, 0) + 1
        return ["event_type", "severity", "events"], [(*key, count) for key, count in sorted(counts.items())]
    if query_name == "auth_failures":
        filtered = [r for r in records if r["event_type"] == "auth_failed"]
        return ["timestamp", "service", "src_ip", "status", "severity", "message"], [tuple(r.get(key) for key in ("timestamp", "service", "src_ip", "status", "severity", "message")) for r in filtered]
    if query_name in {"north_south", "east_west"}:
        direction = "north_south" if query_name == "north_south" else "east_west"
        groups: dict[tuple[str, str, str], list[int]] = {}
        for record in records:
            if record.get("direction") == direction:
                key = (direction, record.get("action"), record.get("service"))
                groups.setdefault(key, [0, 0])
                groups[key][0] += 1
                groups[key][1] += int(record.get("bytes") or 0)
        rows = [(*key, values[0], values[1]) for key, values in groups.items()]
        return ["direction", "action", "service", "events", "bytes"], sorted(rows, key=lambda row: (-row[4], row[2]))
    if query_name == "denials":
        filtered = [r for r in records if r["event_type"] == "denial" or r.get("action") == "deny"]
        return ["timestamp", "direction", "service", "src_ip", "dst_port", "severity", "message"], [tuple(r.get(key) for key in ("timestamp", "direction", "service", "src_ip", "dst_port", "severity", "message")) for r in filtered]
    if query_name == "findings":
        # Kept as a compatibility view, but intentionally empty: local data
        # must never be presented as Security Hub findings.
        return ["severity", "finding_type", "findings"], []
    if query_name == "cves":
        # CVEs are also cloud-only; do not create local fixtures for them.
        return ["cve_id", "severity", "findings"], []
    if query_name == "traffic_anomalies":
        detection = detect_traffic_anomalies(records)
        columns = ["signal", "direction", "observed_5m", "baseline_mean_30m", "baseline_sigma_30m", "threshold_30m", "z_score", "status"]
        return columns, [tuple(item[column] for column in columns) for item in detection["signals"]]
    raise ValueError(f"unknown query '{query_name}'")


def prometheus_metrics(events_path: Path) -> str:
    """Return low-cardinality gauges/counters for a local Prometheus scrape."""
    records = load_records(events_path)
    if not records:
        raise ValueError("event file is empty")
    latest = max(parse_start(record["timestamp"]) for record in records)
    window_start = latest - timedelta(minutes=5)
    recent_records = [record for record in records if parse_start(record["timestamp"]) >= window_start]

    def aggregate(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in source:
            key = (record.get("event_type"), record.get("direction"), record.get("service"), record.get("severity"))
            item = grouped.setdefault(key, {"event_type": key[0], "direction": key[1], "service": key[2], "severity": key[3], "events": 0, "bytes": 0})
            item["events"] += 1
            item["bytes"] += int(record.get("bytes") or 0)
        return list(grouped.values())

    rows = aggregate(records)
    recent = aggregate(recent_records)

    lines: list[str] = []

    def add_group(metric: str, help_text: str, source_rows: Iterable[dict[str, Any]], predicate: Any, value_key: str = "events") -> None:
        lines.extend([f"# HELP {metric} {help_text}", f"# TYPE {metric} gauge"])
        for row in source_rows:
            if predicate(row):
                labels = [f'environment="local-simulated"']
                for key in ("event_type", "direction", "service", "severity"):
                    if row[key] is not None:
                        labels.append(f'{key}="{row[key]}"')
                lines.append(f"{metric}{{{','.join(labels)}}} {row[value_key]}")

    add_group("network_security_events_total", "Total simulated security events", rows, lambda row: True)
    add_group("network_security_auth_failures_5m", "Simulated failed authentications in the last five dataset minutes", recent, lambda row: row["event_type"] == "auth_failed")
    add_group("network_security_denials_5m", "Simulated denials in the last five dataset minutes", recent, lambda row: row["event_type"] == "denial")
    add_group("network_security_flow_bytes_total", "Simulated flow bytes grouped by direction", rows, lambda row: row["event_type"] == "flow", "bytes")
    detection = detect_traffic_anomalies(records)
    lines.extend([
        "# HELP network_security_traffic_anomaly Traffic anomaly state; 1 means the fixed rule detected a spike",
        "# TYPE network_security_traffic_anomaly gauge",
        "# HELP network_security_traffic_observed_5m Observed traffic signal value in the latest five-minute window",
        "# TYPE network_security_traffic_observed_5m gauge",
        "# HELP network_security_traffic_baseline_mean_30m Mean signal value in the isolated thirty-minute baseline",
        "# TYPE network_security_traffic_baseline_mean_30m gauge",
        "# HELP network_security_traffic_baseline_sigma_30m Population standard deviation in the isolated baseline",
        "# TYPE network_security_traffic_baseline_sigma_30m gauge",
        "# HELP network_security_traffic_threshold_30m Detection threshold baseline plus two sigma",
        "# TYPE network_security_traffic_threshold_30m gauge",
    ])
    for item in detection["signals"]:
        labels = f'environment="local-simulated",signal="{item["signal"]}",direction="{item["direction"]}"'
        lines.append(f'network_security_traffic_anomaly{{{labels}}} {int(item["anomalous"])}')
        lines.append(f'network_security_traffic_observed_5m{{{labels}}} {item["observed_5m"]}')
        lines.append(f'network_security_traffic_baseline_mean_30m{{{labels}}} {item["baseline_mean_30m"]}')
        lines.append(f'network_security_traffic_baseline_sigma_30m{{{labels}}} {item["baseline_sigma_30m"]}')
        lines.append(f'network_security_traffic_threshold_30m{{{labels}}} {item["threshold_30m"]}')
    lines.append("network_security_dataset_latest_timestamp{environment=\"local-simulated\"} " + str(latest.timestamp()))
    return "\n".join(lines) + "\n"


def print_table(headers: list[str], rows: list[tuple[Any, ...]]) -> None:
    print(json.dumps({"columns": headers, "rows": rows}, ensure_ascii=False, indent=2))


class MetricsHandler(BaseHTTPRequestHandler):
    events_path: Path

    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        if self.path == "/health":
            body = b'{"status":"ok","environment":"local-simulated"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path == "/metrics":
            body = prometheus_metrics(self.events_path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
        else:
            body = b'{"error":"use /health or /metrics"}\n'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def command_generate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / name for name in ("security-events.jsonl", "security-events.csv", "simulation-summary.json")]
    if not args.force:
        existing = [str(path) for path in paths if path.exists()]
        if existing:
            raise RuntimeError("output exists; choose an empty directory or pass --force: " + ", ".join(existing))
    start = parse_start(args.start)
    records = generate_events(start, args.seed)
    write_jsonl(paths[0], records)
    write_csv(paths[1], records)
    paths[2].write_text(json.dumps(summary(records, start, args.seed), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "files": [path.name for path in paths], "event_count": len(records), "seed": args.seed, "start": iso_utc(start)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="create deterministic JSONL, CSV and summary outputs")
    generate.add_argument("--output-dir", required=True)
    generate.add_argument("--start", default="2026-01-01T00:00:00Z", help="UTC ISO-8601 start timestamp")
    generate.add_argument("--seed", type=int, default=20260101)
    generate.add_argument("--force", action="store_true", help="overwrite the three named output files")
    generate.set_defaults(handler=command_generate)

    query = subparsers.add_parser("query", help="run one of the documented JSONL queries")
    query.add_argument("--events", required=True, help="path to security-events.jsonl")
    query.add_argument("--name", choices=QUERY_NAMES, required=True)
    query.set_defaults(handler=lambda args: (print_table(*query_rows(Path(args.events), args.name)) or 0))

    metrics = subparsers.add_parser("metrics", help="print Prometheus exposition for the local dataset")
    metrics.add_argument("--events", required=True, help="path to security-events.jsonl")

    def command_metrics(args: argparse.Namespace) -> int:
        sys.stdout.write(prometheus_metrics(Path(args.events)))
        return 0
    metrics.set_defaults(handler=command_metrics)

    serve = subparsers.add_parser("serve", help="serve /health and /metrics for a local dashboard")
    serve.add_argument("--events", required=True, help="path to security-events.jsonl")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=9464)

    def command_serve(args: argparse.Namespace) -> int:
        handler = type("BoundMetricsHandler", (MetricsHandler,), {"events_path": Path(args.events).resolve()})
        server = ThreadingHTTPServer((args.host, args.port), handler)
        print(f"serving local-simulated metrics on http://{args.host}:{args.port}/metrics")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0
        finally:
            server.server_close()
    serve.set_defaults(handler=command_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
