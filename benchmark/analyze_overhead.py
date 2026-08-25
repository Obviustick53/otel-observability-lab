"""Compara los resultados JSON generados por k6."""

import json
from pathlib import Path
from typing import Optional


def load(mode: str) -> dict:
    path = Path(f"benchmark/raw/results_{mode}.json")
    if not path.exists():
        raise SystemExit(f"No existe {path}. Ejecuta primero el benchmark {mode}.")
    return json.loads(path.read_text(encoding="utf-8"))


def percentage(baseline: float, instrumented: float) -> Optional[float]:
    if baseline == 0:
        return None
    return ((instrumented - baseline) / baseline) * 100


def main() -> None:
    baseline = load("baseline")
    instrumented = load("otel")
    base_metrics = baseline["metrics"]
    otel_metrics = instrumented["metrics"]

    rows = [
        ("Latencia promedio (ms)", "latency_avg_ms"),
        ("Latencia p95 (ms)", "latency_p95_ms"),
        ("Latencia p99 (ms)", "latency_p99_ms"),
        ("Throughput (req/s)", "throughput_rps"),
        ("Tasa de error (%)", "error_rate_pct"),
    ]

    print("| Metrica | Baseline | Con OTel | Delta % |")
    print("|---|---:|---:|---:|")
    for label, key in rows:
        base = float(base_metrics.get(key, 0))
        otel = float(otel_metrics.get(key, 0))
        delta = percentage(base, otel)
        delta_text = "N/A" if delta is None else f"{delta:+.2f}%"
        print(f"| {label} | {base:.2f} | {otel:.2f} | {delta_text} |")

    p99_delta = float(otel_metrics.get("latency_p99_ms", 0)) - float(base_metrics.get("latency_p99_ms", 0))
    print(f"\nLatencia adicional p99: {p99_delta:+.2f} ms")


if __name__ == "__main__":
    main()
