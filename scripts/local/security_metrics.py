"""Small, dependency-free exporter for local/simulated security signals.

This is deliberately not a VPC Flow Logs implementation. It provides stable
labels and deterministic values so the local Grafana dashboard can be tested
without implying that AWS security telemetry was executed.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import time


ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
TELEMETRY_SCOPE = os.getenv("TELEMETRY_SCOPE", "simulated")
STARTED_AT = time.time()
COUNTERS = {
    "auth_failures": 3,
    "network_denied": 2,
    "inbound_bytes": 4096,
    "east_west_connections": 7,
    "findings": 1,
}


def metrics_payload() -> bytes:
    # Advancing on scrape keeps rate() panels useful while remaining
    # deterministic and clearly marked simulated.
    COUNTERS["auth_failures"] += 1
    COUNTERS["network_denied"] += 1
    COUNTERS["inbound_bytes"] += 4096
    COUNTERS["east_west_connections"] += 4
    labels = (
        f'environment="{ENVIRONMENT}",'
        f'telemetry_scope="{TELEMETRY_SCOPE}",'
        'source="local-security-simulator"'
    )
    lines = [
        "# HELP local_security_auth_failures_total Simulated failed authentications.",
        "# TYPE local_security_auth_failures_total counter",
        f"local_security_auth_failures_total{{{labels}}} {COUNTERS['auth_failures']}",
        "# HELP local_security_network_denied_total Simulated denied network flows.",
        "# TYPE local_security_network_denied_total counter",
        f"local_security_network_denied_total{{{labels}}} {COUNTERS['network_denied']}",
        "# HELP local_security_inbound_bytes_total Simulated north-south bytes.",
        "# TYPE local_security_inbound_bytes_total counter",
        f"local_security_inbound_bytes_total{{{labels}}} {COUNTERS['inbound_bytes']}",
        "# HELP local_security_east_west_connections_total Simulated east-west connections.",
        "# TYPE local_security_east_west_connections_total counter",
        f"local_security_east_west_connections_total{{{labels}}} {COUNTERS['east_west_connections']}",
        "# HELP local_security_findings_total Simulated Security Hub findings.",
        "# TYPE local_security_findings_total counter",
        f"local_security_findings_total{{{labels},severity=\"medium\"}} {COUNTERS['findings']}",
        "# HELP local_security_simulator_uptime_seconds Local simulator uptime.",
        "# TYPE local_security_simulator_uptime_seconds gauge",
        f"local_security_simulator_uptime_seconds{{{labels}}} {time.time() - STARTED_AT:.3f}",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
        elif self.path == "/metrics":
            body = metrics_payload()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        else:
            body = b"not found\n"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9464), Handler).serve_forever()
