import json
import unittest
from pathlib import Path

from aiops.correlator import compare, evaluate


class CorrelatorTests(unittest.TestCase):
    def test_requires_both_conditions(self):
        window = {
            "service": "service-b", "environment": "local", "window_start": "a", "window_end": "b",
            "observed_error_rate": 0.2, "baseline_mean": 0.01, "baseline_sigma": 0.01,
            "latency_p99_seconds": 0.1, "slo_latency_p99_seconds": 0.5,
        }
        self.assertFalse(evaluate(window)["dynamic_trigger"])

    def test_fixture_comparison_is_reproducible(self):
        fixture = json.loads(Path("aiops/fixtures/correlation-windows.json").read_text())
        result = compare(fixture["windows"])
        self.assertEqual(result["windows_evaluated"], 3)
        self.assertEqual(result["dynamic_rule"]["incidents_detected"], 1)
        self.assertEqual(result["static_rule"]["incidents_detected"], 2)
        self.assertEqual(result["rows"][2]["trace_id"], "unknown")


if __name__ == "__main__":
    unittest.main()
