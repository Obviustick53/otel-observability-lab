# Evidencia: benchmark con OTel

## Objetivo

Medir el comportamiento del mismo flujo de negocio con la instrumentación OpenTelemetry activa y comparar sus resultados contra el baseline.

## Configuración

| Parámetro | Valor |
|---|---|
| Modo | `otel` |
| Usuarios virtuales | 50 |
| Calentamiento | 30 segundos |
| Carga sostenida | 5 minutos |
| Endpoint | `http://localhost:8000/order/{order_id}` |
| Exportación | OTLP hacia el OTel Collector |
| Herramienta | k6 ejecutado en Docker |

## Comandos ejecutados

```powershell
docker compose up -d --build service-b service-a
```

```powershell
docker run --rm -i `
  -v "${PWD}:/workspace" `
  -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=otel `
  -e VUS=50 `
  -e WARMUP=30s `
  -e DURATION=5m `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
```

La medición de recursos se guardó en [`otel-resources.txt`](otel-resources.txt) y la salida de k6 en [`otel-k6-console.txt`](otel-k6-console.txt).

## Resultado de k6

```json
{
  "mode": "otel",
  "timestamp": "2026-08-25T04:14:10.546Z",
  "vus": 50,
  "warmup": "30s",
  "duration": "5m",
  "metrics": {
    "latency_avg_ms": 776.29252730158,
    "latency_p95_ms": 1293.0835285,
    "latency_p99_ms": 1585.6362096999999,
    "throughput_rps": 42.430163900961226,
    "error_rate_pct": 0
  }
}
```

Resumen: se completaron 14 035 iteraciones, con 0 iteraciones interrumpidas y 0 % de errores.

## CPU y memoria

Se obtuvieron ocho muestras con valores de `docker stats` durante la fase útil de la carga. Las últimas cuatro iteraciones del transcript ocurrieron después de finalizar k6 y no imprimieron filas de contenedores.

| Servicio | CPU promedio | CPU máxima | Memoria promedio | Memoria máxima |
|---|---:|---:|---:|---:|
| service-a | 1.308 % | 3.68 % | 52.80 MiB | 53.78 MiB |
| service-b | 0.661 % | 1.07 % | 50.32 MiB | 51.50 MiB |

## Resultado

**APROBADO**: la ejecución instrumentada completó cinco minutos de carga con 50 usuarios virtuales y 0 % de errores, generando simultáneamente telemetría para el Collector.
