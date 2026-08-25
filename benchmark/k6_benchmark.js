import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const MODE = __ENV.MODE || "otel";
const VUS = Number(__ENV.VUS || 50);
const WARMUP = __ENV.WARMUP || "30s";
const DURATION = __ENV.DURATION || "5m";

export const options = {
  scenarios: {
    warmup: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: WARMUP, target: VUS },
      ],
      gracefulRampDown: "10s",
    },
    sustained: {
      executor: "constant-vus",
      vus: VUS,
      duration: DURATION,
      startTime: WARMUP,
      gracefulStop: "10s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(99)<2000"],
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

export function setup() {
  const health = http.get(`${BASE_URL}/health`);
  check(health, { "service-a is healthy": (response) => response.status === 200 });
  return { mode: MODE };
}

export default function (data) {
  const orderId = `ord-00${(__VU % 3) + 1}`;
  const response = http.get(`${BASE_URL}/order/${orderId}`, {
    tags: { mode: data.mode, endpoint: "order" },
    timeout: "10s",
  });

  check(response, {
    "status is 200": (r) => r.status === 200,
    "response has order": (r) => r.body && r.body.includes("order"),
    "OTel response has trace_id": (r) => data.mode === "baseline" || r.body.includes("trace_id"),
  });

  sleep(0.2 + Math.random() * 0.3);
}

export function handleSummary(data) {
  const metrics = data.metrics;
  const output = {
    mode: MODE,
    timestamp: new Date().toISOString(),
    vus: VUS,
    warmup: WARMUP,
    duration: DURATION,
    metrics: {
      latency_avg_ms: metrics.http_req_duration?.values?.avg || 0,
      latency_p95_ms: metrics.http_req_duration?.values?.["p(95)"] || 0,
      latency_p99_ms: metrics.http_req_duration?.values?.["p(99)"] || 0,
      throughput_rps: metrics.http_reqs?.values?.rate || 0,
      error_rate_pct: (metrics.http_req_failed?.values?.rate || 0) * 100,
    },
  };

  return {
    stdout: JSON.stringify(output, null, 2),
    [`benchmark/raw/results_${MODE}.json`]: JSON.stringify(output, null, 2),
  };
}
