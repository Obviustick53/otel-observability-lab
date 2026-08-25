# Pipeline de Observabilidad End-to-End con OpenTelemetry

Proyecto académico propio para construir un pipeline local de observabilidad sobre dos microservicios:

`cliente/k6 → service-a → service-b → PostgreSQL`

La solución emite las tres señales:

- Trazas distribuidas mediante OTLP hacia Jaeger.
- Métricas mediante OTLP hacia el Collector y luego Prometheus.
- Logs JSON mediante stdout y OTLP hacia el Collector y luego Loki.

La evidencia principal se generará localmente para evitar costos innecesarios en GCP y AWS. La infraestructura cloud se documentará en `infra/` como trabajo reproducible.

## Estado actual

El laboratorio local es ejecutable y validado: los dos servicios generan trazas, métricas y logs; el Collector los enruta a Jaeger, Prometheus y Loki; y Grafana los visualiza.

## Cómo iniciar el laboratorio

1. Abrir Docker Desktop y esperar a que indique que Docker está ejecutándose.
2. Desde la raíz del repositorio, ejecutar `docker compose up -d --build`.
3. Verificar los contenedores con `docker compose ps`.
4. Consultar `http://localhost:8000/order/ord-001`.
5. Abrir Jaeger en `http://localhost:16686`.
6. Abrir Prometheus en `http://localhost:9090`.
7. Abrir Grafana en `http://localhost:3000` usando `admin/admin`.

Para detener el laboratorio se utiliza `docker compose down`. Para eliminar también los datos persistentes locales se utiliza `docker compose down -v`.

## Qué se validará

1. Instrumentación HTTP de FastAPI.
2. Instrumentación de llamadas HTTP entre servicios.
3. Instrumentación de PostgreSQL.
4. Spans personalizados de lógica de negocio.
5. Logs JSON con `trace_id` y `span_id`.
6. Métricas de solicitudes, latencia, solicitudes activas y consultas de base de datos.
7. Propagación W3C `traceparent` entre servicios.
8. Dashboard Grafana con seis paneles.
9. Correlación log ↔ traza usando `trace_id`.
10. Benchmark baseline versus OTel.

## Estructura

```text
otel-observability-lab/
├── service-a/
├── service-b/
├── otel-collector/
├── prometheus/
├── grafana/
├── loki/
├── infra/
│   ├── gcp/
│   └── aws/
├── benchmark/
├── screenshots/
├── docs/
├── report/
├── docker-compose.yaml
├── .gitignore
└── README.md
```

## Requisitos locales

- Docker Desktop
- Git
- k6 o Docker Desktop para ejecutar el contenedor oficial de k6
- Google Cloud CLI, únicamente para validar posteriormente GKE
- AWS CLI, únicamente para validar posteriormente ECS
- Terraform o Helm, según la estrategia final de infraestructura

## Modos del benchmark

Los servicios respetan la variable `OTEL_SDK_DISABLED`:

- `false`: instrumentación completa y exportación al Collector.
- `true`: baseline sin SDK OTel activo.

El mismo script de k6 se ejecutará en ambos modos para comparar latencia, throughput y errores. La CPU y memoria se medirán por separado durante las ejecuciones.

Para ejecutar el baseline sin instrumentación OTel, activar el override de Compose:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.baseline.yaml up -d --build service-b service-a
docker run --rm -i -v "${PWD}:/workspace" -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=baseline -e VUS=50 -e DURATION=5m `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
```

Después, volver al modo instrumentado y ejecutar la segunda medición:

```powershell
docker compose up -d --build service-b service-a
docker run --rm -i -v "${PWD}:/workspace" -w /workspace `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e MODE=otel -e VUS=50 -e DURATION=5m `
  grafana/k6 run /workspace/benchmark/k6_benchmark.js
python benchmark/analyze_overhead.py
```

Para una prueba rápida antes de la ejecución oficial de cinco minutos se puede usar `-e DURATION=30s -e VUS=5`. La evidencia final debe conservar el escenario recomendado de 50 usuarios concurrentes durante cinco minutos.

## Regla de seguridad

No se deben subir al repositorio credenciales, claves privadas, archivos ADC, access keys, secretos ni archivos `.env` reales.

## Evidencia esperada

Las evidencias se almacenarán en `screenshots/` y los resultados crudos del benchmark en `benchmark/raw/`. El reporte final se almacenará en `report/`.

El procedimiento detallado para generar las capturas está en [`docs/evidence-checklist.md`](docs/evidence-checklist.md).

La guía para publicar este repositorio en tu cuenta propia está en [`docs/github-publish.md`](docs/github-publish.md).
