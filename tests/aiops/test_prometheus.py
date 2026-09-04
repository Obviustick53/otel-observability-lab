import unittest

from aiops.correlator import correlate
from aiops.prometheus import ERROR_QUERY, P99_QUERY, PrometheusClient, collect_live_samples


def instant(service, value, timestamp=1_000.0):
    return {"metric": {"service_name": service}, "value": [timestamp, str(value)]}


def ranged(service, values, start=0.0, step=15.0):
    return {
        "metric": {"service_name": service},
        "values": [[start + index * step, str(value)] for index, value in enumerate(values)],
    }


class FakePrometheus(PrometheusClient):
    def __init__(self, finite_p99=True):
        super().__init__("http://fake-prometheus")
        self.finite_p99 = finite_p99

    def query(self, expression, evaluation_time=None):
        if expression == ERROR_QUERY:
            return [instant("service-b", 0.10, 4_000.0)]
        if expression == P99_QUERY:
            return [instant("service-b", 0.60 if self.finite_p99 else "NaN", 4_000.0)]
        raise AssertionError(f"unexpected query: {expression}")

    def query_range(self, expression, start, end, step):
        if expression == ERROR_QUERY:
            if end < 3_900:
                return [ranged("service-b", [0.01, 0.01, 0.02], start=start, step=step)]
            return [ranged("service-b", [0.10, 0.10], start=start, step=step)]
        if expression == P99_QUERY:
            value = 0.60 if self.finite_p99 else "NaN"
            return [ranged("service-b", [value, value], start=start, step=step)]
        raise AssertionError(f"unexpected range query: {expression}")


class PrometheusCollectionTests(unittest.TestCase):
    def test_uses_frozen_baseline_and_emits_unknown_trace(self):
        result = collect_live_samples(
            FakePrometheus(),
            evaluation_end=4_000.0,
            evaluation_window_minutes=1,
            baseline_window_minutes=1,
            baseline_exclusion_minutes=1,
            step_seconds=15,
        )
        self.assertEqual(result["status"], "VERIFICADO")
        self.assertEqual(len(result["samples"]), 1)
        sample = result["samples"][0]
        self.assertLessEqual(sample.baseline_window_end_utc, sample.window_start_utc)
        event = correlate(sample)
        self.assertTrue(event["conditions"]["correlated_incident"])
        self.assertEqual(event["trace_id"], "unknown")
        self.assertEqual(event["evidence_class"], "live_local_prometheus")
        self.assertGreater(result["comparisons"]["service-b"]["dynamic_alert_points"], 0)
        self.assertIsNone(result["comparisons"]["service-b"]["false_positives"])

    def test_nan_p99_is_blocked_and_never_treated_as_zero(self):
        result = collect_live_samples(
            FakePrometheus(finite_p99=False),
            evaluation_end=4_000.0,
            evaluation_window_minutes=1,
            baseline_window_minutes=1,
            baseline_exclusion_minutes=1,
            step_seconds=15,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["samples"], [])
        self.assertTrue(any("p99" in limitation for limitation in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
