# Procedimiento del benchmark de overhead

El benchmark compara el mismo flujo HTTP en dos condiciones:

- `baseline`: los servicios funcionan, pero `OTEL_SDK_DISABLED=true`.
- `otel`: los servicios emiten trazas, métricas y logs al Collector.

El escenario oficial usa 50 usuarios virtuales, una rampa de 30 segundos y cinco minutos de carga sostenida. Antes de la ejecución oficial se recomienda usar cinco usuarios y 30 segundos para comprobar que el entorno responde.

## Prechequeo rápido

```powershell
docker compose up -d --build
docker run --rm -i -v "${PWD}:/workspace" -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=otel -e VUS=5 -e WARMUP=5s -e DURATION=30s `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
```

## Ejecución baseline

Terminal 1:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.baseline.yaml up -d --build service-b service-a
```

Terminal 2:

```powershell
docker run --rm -i -v "${PWD}:/workspace" -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=baseline -e VUS=50 -e DURATION=5m `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
```

El resultado queda en `benchmark/raw/results_baseline.json`.

## Ejecución con OTel

Primero restaurar los servicios instrumentados:

```powershell
docker compose up -d --build service-b service-a
```

Luego ejecutar:

```powershell
docker run --rm -i -v "${PWD}:/workspace" -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=otel -e VUS=50 -e DURATION=5m `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
```

El resultado queda en `benchmark/raw/results_otel.json`.

## Medición de CPU y memoria

Mientras k6 está ejecutándose, abrir una tercera terminal y consultar varias veces:

```powershell
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

Registrar para `service-a` y `service-b` el valor máximo o el promedio de cinco lecturas tomadas durante la fase sostenida. Repetir el mismo procedimiento para baseline y OTel.

En el reporte, sumar ambos servicios y calcular:

```text
CPU overhead (%) = ((CPU OTel - CPU baseline) / CPU baseline) * 100
Memoria adicional (MB) = Memoria OTel - Memoria baseline
```

Si el baseline tiene un consumo muy pequeño, reportar también la diferencia absoluta en CPU y no únicamente el porcentaje, para evitar una interpretación exagerada por división entre un número cercano a cero.

## Análisis final

Cuando existan los dos JSON:

```powershell
python benchmark/analyze_overhead.py
```

La salida contiene latencia promedio, p95, p99, throughput, tasa de error y delta porcentual. Copiar esa tabla al reporte técnico y agregar dos filas para CPU y memoria con las mediciones de `docker stats`.
