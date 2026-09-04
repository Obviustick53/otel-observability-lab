import json
import unittest
from pathlib import Path

from aiops.correlator import CorrelationConfig, MetricSample, compare_rules, correlate


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_cases.json"


def sample(**overrides):
    value = {
        "service": "service-b",
        "environment": "test",
        "window_start_utc": "2026-09-01T00:00:00Z",
        "window_end_utc": "2026-09-01T00:01:00Z",
        "timestamp_utc": "2026-09-01T00:00:59Z",
        "error_rate": 0.10,
        "latency_p99_ms": 600.0,
        "baseline_error_rate": 0.01,
        "sigma_error_rate": 0.02,
        "slo_latency_p99_ms": 500.0,
        "trace_id": "unknown",
        "trace_id_resolution": "unknown",
        "trace_id_limitation": "No trace in unit test fixture.",
    }
    value.update(overrides)
    return value


class CorrelatorContractTests(unittest.TestCase):
    def test_requires_both_dynamic_error_and_latency_slo(self):
        self.assertTrue(correlate(sample())["conditions"]["correlated_incident"])
        event = correlate(sample(latency_p99_ms=500.0))
        self.assertFalse(event["conditions"]["correlated_incident"])
        self.assertTrue(event["conditions"]["error_rate_above_dynamic"])
        self.assertFalse(event["conditions"]["latency_p99_above_slo"])

    def test_dynamic_boundary_is_strictly_greater_than(self):
        event = correlate(sample(error_rate=0.05, baseline_error_rate=0.01, sigma_error_rate=0.02))
        self.assertEqual(event["thresholds"]["dynamic_error_rate"], 0.05)
        self.assertFalse(event["conditions"]["error_rate_above_dynamic"])
        self.assertFalse(event["conditions"]["correlated_incident"])

    def test_unknown_trace_is_explicit_and_invalid_ids_are_rejected(self):
        event = correlate(sample())
        self.assertEqual(event["trace_id"], "unknown")
        self.assertEqual(event["trace_id_limitation"], "No trace in unit test fixture.")
        with self.assertRaises(ValueError):
            MetricSample.from_mapping(sample(trace_id="made-up-trace"))

    def test_declared_baseline_must_end_before_evaluation_window(self):
        with self.assertRaises(ValueError):
            MetricSample.from_mapping(sample(
                baseline_window_start_utc="2026-09-01T00:00:00Z",
                baseline_window_end_utc="2026-09-01T00:01:00Z",
            ))

    def test_event_id_is_reproducible(self):
        self.assertEqual(correlate(sample()), correlate(sample()))

    def test_comparison_counts_noise_detection_and_ttd(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        config = CorrelationConfig(
            static_error_rate_threshold=fixture["static_thresholds"]["error_rate"],
            static_latency_p99_ms_threshold=fixture["static_thresholds"]["latency_p99_ms"],
        )
        result = compare_rules(fixture["cases"], config)
        self.assertEqual(result["dynamic_rule"]["alerts"], 2)
        self.assertEqual(result["dynamic_rule"]["false_positives"], 0)
        self.assertEqual(result["dynamic_rule"]["incidents_detected"], 2)
        self.assertEqual(result["static_rule"]["alerts"], 2)
        self.assertEqual(result["static_rule"]["false_positives"], 1)
        self.assertEqual(result["static_rule"]["incidents_detected"], 1)
        self.assertEqual(result["static_rule"]["incidents_missed"], 1)
        self.assertEqual(result["noise_comparison"]["false_positive_reduction_pct_vs_static"], 100.0)
        self.assertEqual(result["dynamic_rule"]["mean_ttd_seconds"], 44.0)


if __name__ == "__main__":
    unittest.main()
