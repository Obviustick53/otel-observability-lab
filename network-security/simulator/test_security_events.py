import json
import tempfile
import unittest
from pathlib import Path

from security_events import (
    detect_traffic_anomalies,
    generate_events,
    iso_utc,
    parse_start,
    prometheus_metrics,
    query_rows,
    write_jsonl,
)


class SecurityEventSimulatorTests(unittest.TestCase):
    def test_generation_is_deterministic(self):
        start = parse_start("2026-01-01T00:00:00Z")
        first = generate_events(start, 123)
        second = generate_events(start, 123)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 128)
        self.assertEqual(first[0]["environment"], "local-simulated")
        self.assertTrue(all(item["source"] == "network-security-simulator" for item in first))
        self.assertFalse(any(item["event_type"] == "finding" for item in first))
        self.assertFalse(any(item.get("cve_id") for item in first))

    def test_categories_and_denials_are_queryable(self):
        records = generate_events(parse_start("2026-01-01T00:00:00Z"), 123)
        event_types = {record["event_type"] for record in records}
        self.assertEqual(event_types, {"auth_failed", "auth_success", "flow", "denial"})
        self.assertGreaterEqual(sum(record["event_type"] == "auth_failed" for record in records), 10)
        self.assertEqual(sum(record["event_type"] == "denial" for record in records), 16)
        self.assertEqual(sum(record["cve_id"] is not None for record in records), 0)

    def test_traffic_anomaly_is_isolated_from_recent_burst(self):
        records = generate_events(parse_start("2026-01-01T00:00:00Z"), 123)
        detection = detect_traffic_anomalies(records)
        by_signal = {item["signal"]: item for item in detection["signals"]}
        self.assertEqual(by_signal["rejected_flows"]["status"], "DETECTED")
        self.assertEqual(by_signal["rejected_flows"]["baseline_mean_30m"], 0.0)
        self.assertEqual(by_signal["rejected_flows"]["baseline_sigma_30m"], 0.0)
        self.assertGreater(by_signal["rejected_flows"]["observed_5m"], 0)

    def test_cloud_only_views_are_empty(self):
        events = generate_events(parse_start("2026-01-01T00:00:00Z"), 123)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            write_jsonl(path, events)
            self.assertEqual(query_rows(path, "findings")[1], [])
            self.assertEqual(query_rows(path, "cves")[1], [])

    def test_jsonl_and_metrics_have_no_trace_id_label(self):
        records = generate_events(parse_start("2026-01-01T00:00:00Z"), 123)
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / "events.jsonl"
            write_jsonl(events, records)
            self.assertEqual(len(events.read_text(encoding="utf-8").splitlines()), 128)
            metrics = prometheus_metrics(events)
            self.assertIn('environment="local-simulated"', metrics)
            self.assertNotIn("trace_id=", metrics)
            self.assertIn("network_security_traffic_anomaly", metrics)
            self.assertNotIn("network_security_findings", metrics)

    def test_iso_utc_round_trip(self):
        value = parse_start("2026-01-01T01:02:03-05:00")
        self.assertEqual(iso_utc(value), "2026-01-01T06:02:03Z")


if __name__ == "__main__":
    unittest.main()
