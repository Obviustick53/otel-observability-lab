# Evidencia: benchmark baseline sin OTel

## Objetivo

Establecer una línea base de rendimiento ejecutando los microservicios sin el SDK de OpenTelemetry activo. Esta medición permite comparar la latencia, el throughput, los errores, el CPU y la memoria frente a la versión instrumentada.

## Configuración

| Parámetro | Valor |
|---|---|
| Modo | `baseline` |
| Usuarios virtuales | 50 |
| Calentamiento | 30 segundos |
| Carga sostenida | 5 minutos |
| Endpoint | `http://localhost:8000/order/{order_id}` |
| Instrumentación | `OTEL_SDK_DISABLED=true` |
| Herramienta | k6 ejecutado en Docker |

## Comandos ejecutados

```powershell
docker compose `
  -f docker-compose.yaml `
  -f docker-compose.baseline.yaml `
  up -d --build service-b service-a
```

```powershell
docker run --rm -i `
  -v "${PWD}:/workspace" `
  -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=baseline `
  -e VUS=50 `
  -e WARMUP=30s `
  -e DURATION=5m `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
```

La medición de recursos se guardó en [`baseline-resources.txt`](baseline-resources.txt) y la salida de k6 en [`baseline-k6-console.txt`](baseline-k6-console.txt).

## Resultado de k6

```json
{
  "mode": "baseline",
  "timestamp": "2026-08-25T03:59:13.491Z",
  "vus": 50,
  "warmup": "30s",
  "duration": "5m",
  "metrics": {
    "latency_avg_ms": 538.6984777856673,
    "latency_p95_ms": 938.0004953000001,
    "latency_p99_ms": 1138.1410584800003,
    "throughput_rps": 53.70301838089688,
    "error_rate_pct": 0
  }
}
```

Resumen: se completaron 17 766 iteraciones, con 0 iteraciones interrumpidas y 0 % de errores.

## CPU y memoria

Se obtuvieron ocho muestras con valores de `docker stats` antes de que terminara la carga. Las últimas cuatro iteraciones del transcript ocurrieron después de finalizar k6 y no imprimieron filas de contenedores.

| Servicio | CPU promedio | CPU máxima | Memoria promedio | Memoria máxima |
|---|---:|---:|---:|---:|
| service-a | 0.244 % | 0.28 % | 52.61 MiB | 52.82 MiB |
| service-b | 0.566 % | 2.75 % | 50.18 MiB | 50.38 MiB |

El valor máximo de CPU de `service-b` corresponde a un pico aislado de 2.75 % y se conserva en la evidencia para no ocultar variaciones durante la ejecución.

## Resultado

**APROBADO**: el baseline completó cinco minutos de carga con 50 usuarios virtuales y 0 % de errores.
