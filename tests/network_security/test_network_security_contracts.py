import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SIMULATOR = ROOT / "network-security" / "simulator"
sys.path.insert(0, str(SIMULATOR))

from security_events import generate_events, parse_start, prometheus_metrics  # noqa: E402


class NetworkSecurityContractsTests(unittest.TestCase):
    def test_dashboard_uses_exported_metrics_and_explicit_source(self):
        dashboard = json.loads((ROOT / "grafana" / "dashboards" / "security-network.json").read_text(encoding="utf-8"))
        text = json.dumps(dashboard, ensure_ascii=False)
        self.assertIn("network_security_traffic_anomaly", text)
        self.assertIn('environment=\\\"local-simulated\\\"', text)
        self.assertNotIn("local_security_auth_failures_total", text)
        self.assertNotIn("network_security_findings", text)
        self.assertIn("BLOQUEADO", text)

    def test_prometheus_contract_has_only_low_cardinality_security_signals(self):
        records = generate_events(parse_start("2026-01-01T00:00:00Z"), 123)
        metrics = prometheus_metrics_from_records(records)
        self.assertIn('network_security_traffic_anomaly{environment="local-simulated",signal="rejected_flows",direction="all"} 1', metrics)
        self.assertNotIn("trace_id=", metrics)
        self.assertNotIn("cve_id=", metrics)
        self.assertNotIn("network_security_findings", metrics)

    def test_cloudformation_keeps_security_hub_gate_and_real_source_controls(self):
        template = (ROOT / "infra" / "aws" / "cloudformation" / "04-security-observability.yaml").read_text(encoding="utf-8")
        self.assertIn("SecurityHubSubscriptionGate:", template)
        self.assertIn("BLOCKED_UNTIL_SUBSCRIPTION_PREFLIGHT", template)
        self.assertIn("EnableSecurityHub:\n    Type: String\n    Default: 'false'", template)
        self.assertIn("AWS::Logs::MetricFilter", template)
        self.assertIn("VpcRejectAnomalyAlarm:", template)
        self.assertIn("CloudTrailAuthFailureMetricFilter:", template)
        self.assertNotIn("synthetic finding; not", template.lower())

    def test_sql_does_not_query_local_findings_or_cves(self):
        queries = (ROOT / "network-security" / "queries" / "security_queries.sql").read_text(encoding="utf-8")
        self.assertNotIn("event_type = 'finding'", queries)
        self.assertNotIn("cve_id IS NOT NULL", queries)
        self.assertIn("after subscription preflight", queries)


def prometheus_metrics_from_records(records):
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "security-events.jsonl"
        path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        return prometheus_metrics(path)


if __name__ == "__main__":
    unittest.main()
