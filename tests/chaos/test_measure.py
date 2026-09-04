import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from chaos.measure import build_report, parse_timestamp, percentile  # noqa: E402


def record(phase, timestamp, status=200, duration=0.05, trace_id="trace-1"):
    return {
        "phase": phase,
        "started_utc": timestamp,
        "completed_utc": timestamp,
        "timestamp_utc": timestamp,
        "status_code": status,
        "duration_seconds": duration,
        "trace_id": trace_id,
    }


def metadata(started="2026-09-03T12:00:00Z"):
    return {
        "experiment": "data-service-errors",
        "environment": "local",
        "telemetry_scope": "local-executed",
        "chaos_parameter": "LAB_DATA_ERROR_RATE=0.1",
        "injection_started_utc": started,
        "load_duration_seconds": 60,
        "baseline_duration_seconds": 60,
        "recovery_duration_seconds": 30,
        "slo_latency_p99_seconds": 0.5,
        "slo_error_rate_budget": 0.005,
        "injection_control": "LAB_DATA_ERROR_RATE",
        "injection_control_value": "0.1",
        "injection_control_observed_value": "0.1",
        "recovery_min_availability": 0.995,
        "rollback_verified": True,
        "stop_conditions": ["bounded timebox", "health check"],
    }


class ChaosMeasureTests(unittest.TestCase):
    def test_percentile_and_timestamp_accept_powershell_fraction(self):
        self.assertEqual(percentile([3, 1, 2], 0.99), 3)
        parsed = parse_timestamp("2026-09-03T12:00:00.1234567Z")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.microsecond, 123456)

    def test_baseline_is_observed_and_frozen_for_local_correlation(self):
        records = [
            record("baseline", "2026-09-03T11:59:00Z", duration=0.05),
            record("baseline", "2026-09-03T11:59:30Z", duration=0.06),
            record("injection", "2026-09-03T12:00:01Z", status=503, duration=0.7),
            record("injection", "2026-09-03T12:00:02Z", status=503, duration=0.8),
            record("recovery", "2026-09-03T12:01:01Z", duration=0.05),
        ]
        report = build_report(records, metadata(), [])
        self.assertEqual(report["baseline"]["status"], "observed")
        self.assertEqual(report["injection_metrics"]["errors"], 2)
        self.assertTrue(report["local_correlation"]["correlated"])
        self.assertIsNone(report["mttd_seconds"])
        self.assertEqual(report["alert_observation"]["classification"], "ALERT_BACKEND_NOT_QUERIED")

    def test_backend_unavailable_does_not_create_alert_or_mttd(self):
        observations = [
            {
                "phase": "injection",
                "prometheus": {"available": False, "alerts": [], "observed_at_utc": "2026-09-03T12:00:10Z"},
                "alertmanager": {"available": False, "alerts": [], "observed_at_utc": "2026-09-03T12:00:10Z"},
            }
        ]
        report = build_report([record("injection", "2026-09-03T12:00:01Z", status=503)], metadata(), observations)
        self.assertEqual(report["alert_observation"]["classification"], "BACKEND_UNAVAILABLE")
        self.assertIsNone(report["firing_timestamp_utc"])
        self.assertIsNone(report["mttd_seconds"])
        self.assertFalse(report["mttd_under_120_seconds"])

    def test_real_firing_timestamp_is_used_for_mttd(self):
        observations = [
            {
                "phase": "injection",
                "prometheus": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:40Z",
                    "alerts": [
                        {
                            "alert_name": "OTelAvailabilityBelowSLO",
                            "state": "firing",
                            "active_at": "2026-09-03T12:00:30Z",
                            "labels": {"service_name": "data-service"},
                            "annotations": {"summary": "real API result"},
                        }
                    ],
                },
                "alertmanager": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:40Z",
                    "alerts": [
                        {
                            "alert_name": "OTelAvailabilityBelowSLO",
                            "status_state": "firing",
                            "starts_at": "2026-09-03T12:00:30Z",
                            "labels": {"service_name": "data-service"},
                            "annotations": {"summary": "real API result"},
                        }
                    ],
                },
            }
        ]
        report = build_report([record("injection", "2026-09-03T12:00:01Z", status=503)], metadata(), observations)
        self.assertEqual(report["alert_observation"]["classification"], "VERIFIED_ALERT_FIRING")
        self.assertEqual(report["firing_timestamp_utc"], "2026-09-03T12:00:30Z")
        self.assertEqual(report["mttd_seconds"], 30)
        self.assertTrue(report["mttd_under_120_seconds"])

    def test_preexisting_alert_is_not_counted_as_new_mttd(self):
        observations = [
            {
                "phase": "baseline",
                "prometheus": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T11:59:40Z",
                    "alerts": [{"alert_name": "OTelAvailabilityBelowSLO", "state": "firing", "active_at": "2026-09-03T11:59:00Z"}],
                },
                "alertmanager": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T11:59:40Z",
                    "alerts": [{"alert_name": "OTelAvailabilityBelowSLO", "status_state": "firing", "starts_at": "2026-09-03T11:59:00Z"}],
                },
            },
            {
                "phase": "injection",
                "prometheus": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:10Z",
                    "alerts": [{"alert_name": "OTelAvailabilityBelowSLO", "state": "firing", "active_at": "2026-09-03T11:59:00Z"}],
                },
                "alertmanager": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:10Z",
                    "alerts": [{"alert_name": "OTelAvailabilityBelowSLO", "status_state": "firing", "starts_at": "2026-09-03T11:59:00Z"}],
                },
            },
        ]
        report = build_report([record("injection", "2026-09-03T12:00:01Z", status=503)], metadata(), observations)
        self.assertEqual(report["alert_observation"]["classification"], "PREEXISTING_ALERT_NO_NEW_FIRING")
        self.assertIsNone(report["mttd_seconds"])

    def test_prometheus_active_at_alone_is_not_firing_timestamp(self):
        observations = [
            {
                "phase": "injection",
                "prometheus": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:40Z",
                    "alerts": [{"alert_name": "OTelAvailabilityBelowSLO", "state": "firing", "active_at": "2026-09-03T12:00:30Z"}],
                },
                "alertmanager": {"available": False, "alerts": [], "observed_at_utc": "2026-09-03T12:00:40Z"},
            }
        ]
        report = build_report([record("injection", "2026-09-03T12:00:01Z", status=503)], metadata(), observations)
        self.assertEqual(report["alert_observation"]["classification"], "FIRING_TIMESTAMP_UNAVAILABLE")
        self.assertIsNone(report["mttd_seconds"])

    def test_firing_cannot_produce_mttd_without_verified_injection_start(self):
        observations = [
            {
                "phase": "injection",
                "prometheus": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:40Z",
                    "alerts": [{"alert_name": "OTelAvailabilityBelowSLO", "state": "firing"}],
                },
                "alertmanager": {
                    "available": True,
                    "observed_at_utc": "2026-09-03T12:00:40Z",
                    "alerts": [
                        {
                            "alert_name": "OTelAvailabilityBelowSLO",
                            "status_state": "firing",
                            "starts_at": "2026-09-03T12:00:30Z",
                        }
                    ],
                },
            }
        ]
        run_metadata = metadata(started=None)
        run_metadata.pop("injection_started_utc")
        report = build_report([], run_metadata, observations)
        self.assertEqual(report["alert_observation"]["classification"], "INJECTION_START_UNAVAILABLE")
        self.assertIsNone(report["firing_timestamp_utc"])
        self.assertIsNone(report["mttd_seconds"])

    def test_observed_phase_boundaries_override_configured_timebox(self):
        records = [
            record("baseline", "2026-09-03T11:59:00Z"),
            record("baseline", "2026-09-03T11:59:10Z"),
            record("injection", "2026-09-03T12:00:00Z", status=503, duration=0.7),
            record("injection", "2026-09-03T12:00:05Z", duration=0.2),
            record("recovery", "2026-09-03T12:00:10Z"),
            record("recovery", "2026-09-03T12:00:15Z"),
        ]
        phases = [
            {"phase": "baseline", "started_utc": "2026-09-03T11:59:00Z", "ended_utc": "2026-09-03T11:59:10Z"},
            {"phase": "injection", "started_utc": "2026-09-03T12:00:00Z", "ended_utc": "2026-09-03T12:00:05Z", "stop_reason": "timebox"},
            {"phase": "recovery", "started_utc": "2026-09-03T12:00:10Z", "ended_utc": "2026-09-03T12:00:15Z"},
        ]
        report = build_report(records, metadata(), [], phase_summaries=phases)
        self.assertEqual(report["injection_metrics"]["duration_seconds"], 5)
        self.assertEqual(report["injection_metrics"]["throughput_requests_per_second"], 0.4)
        self.assertEqual(report["rollback"]["recovery_window_seconds"], 5)
        self.assertTrue(report["rollback"]["recovery_acceptance"]["verified"])

    def test_report_keeps_exact_control_and_execution_classification(self):
        report = build_report(
            [record("recovery", "2026-09-03T12:01:01Z")],
            metadata(),
            [],
        )
        self.assertEqual(report["execution_classification"], "EXECUTED_RECOVERED")
        self.assertEqual(report["injection"]["control_name"], "LAB_DATA_ERROR_RATE")
        self.assertEqual(report["injection"]["control_requested_value"], "0.1")
        self.assertEqual(report["injection"]["control_observed_value"], "0.1")


class ChaosRunnerContractTests(unittest.TestCase):
    def test_runner_keeps_exact_experiments_and_safety_contract(self):
        runner = (REPO_ROOT / "chaos" / "run-experiment.ps1").read_text(encoding="utf-8")
        for fragment in (
            "service-b-latency",
            "data-service-errors",
            "LAB_SERVICE_B_LATENCY_MS",
            "LAB_DATA_ERROR_RATE",
            "controlValue = if ($Experiment -eq 'service-b-latency') { '200' } else { '0.1' }",
            "api/v1/alerts",
            "api/v2/alerts?active=true&silenced=false&inhibited=false",
            "otel:p99_seconds_5m",
            "docker inspect --format '{{.State.StartedAt}}'",
            "injection_start_source = 'docker inspect .State.StartedAt'",
            "[int]$DurationSeconds = 180",
            "targetStopped",
            "stop_condition",
            "finally",
            "compose', 'up', '-d'",
            "recovery",
            "experiment-contract.json",
            "Record-Event",
            "injection_control_observed_value",
            "MaxObservedErrorRate",
            "--phases",
        ):
            self.assertIn(fragment, runner)

    def test_contract_contains_only_the_two_exact_experiments(self):
        contract = json.loads((REPO_ROOT / "chaos" / "experiment-contract.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {item["name"] for item in contract["experiments"]},
            {"service-b-latency", "data-service-errors"},
        )
        values = {item["name"]: item["control"]["value"] for item in contract["experiments"]}
        self.assertEqual(values["service-b-latency"], "200")
        self.assertEqual(values["data-service-errors"], "0.1")
        self.assertTrue(all(item["control"]["rollback_value"] == "0" for item in contract["experiments"]))

    def test_measure_output_is_json_contract(self):
        report = build_report([], metadata(), [])
        json.dumps(report)
        self.assertEqual(report["status"], "executed")
        self.assertIsNone(report["injection_metrics"]["error_rate"])


if __name__ == "__main__":
    unittest.main()
