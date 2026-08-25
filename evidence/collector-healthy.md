# Evidencia: estado saludable del OTel Collector

## Nombre de la evidencia

`collector-healthy`

## Objetivo

Demostrar que el laboratorio local está operativo y que el OTel Collector recibe y procesa las señales de observabilidad emitidas por los microservicios.

Esta evidencia valida:

- disponibilidad de los contenedores principales;
- estado saludable de PostgreSQL, `service-a` y `service-b`;
- ejecución del OTel Collector;
- recepción de trazas;
- recepción de métricas;
- ausencia de errores recientes en el periodo revisado.

## Comandos ejecutados

```powershell
docker compose ps
docker compose logs --since=5m --no-color otel-collector
```

## Interpretación

La salida de `docker compose ps` muestra todos los componentes activos. PostgreSQL, `service-a` y `service-b` aparecen como `healthy`.

Los mensajes `TracesExporter` confirman que el Collector procesó spans. Los mensajes `MetricsExporter` confirman que procesó métricas y puntos de datos.

Durante los últimos cinco minutos no aparecen mensajes `error`, `failed` ni `exception` en la salida del Collector.

## Resultado

**APROBADO**: el pipeline local está activo y el OTel Collector está procesando trazas y métricas correctamente.

## Output completo

```powershell
PS C:\Users\User\Desktop\otel-observability-lab> docker compose ps
NAME                                      IMAGE                                          COMMAND                  SERVICE          CREATED          STATUS                    PORTS
otel-observability-lab-grafana-1          grafana/grafana:11.1.0                         "/run.sh"                grafana          5 hours ago      Up 21 minutes             0.0.0.0:3000->3000/tcp, [::]:3000->3000/tcp
otel-observability-lab-jaeger-1           jaegertracing/all-in-one:1.58                  "/go/bin/all-in-one-…"   jaeger           5 hours ago      Up 5 hours                0.0.0.0:16686->16686/tcp, [::]:16686->16686/tcp
otel-observability-lab-loki-1             grafana/loki:3.0.0                             "/usr/bin/loki -conf…"   loki             5 hours ago      Up 5 hours                0.0.0.0:3100->3100/tcp, [::]:3100->3100/tcp
otel-observability-lab-otel-collector-1   otel/opentelemetry-collector-contrib:0.103.0   "/otelcol-contrib --…"   otel-collector   5 hours ago      Up 4 hours                0.0.0.0:4317-4318->4317-4318/tcp, [::]:4317-4318->4317-4318/tcp, 0.0.0.0:8888-8889->8888-8889/tcp, [::]:8888-8889->8888-8889/tcp, 0.0.0.0:13133->13133/tcp, [::]:13133->13133/tcp
otel-observability-lab-postgres-1         postgres:16-alpine                             "docker-entrypoint.s…"   postgres         5 hours ago      Up 5 hours (healthy)      0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
otel-observability-lab-prometheus-1       prom/prometheus:v2.52.0                        "/bin/prometheus --c…"   prometheus       5 hours ago      Up 5 hours                0.0.0.0:9090->9090/tcp, [::]:9090->9090/tcp
otel-observability-lab-service-a-1        otel-observability-lab-service-a               "uvicorn main:app --…"   service-a        46 minutes ago   Up 46 minutes (healthy)   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
otel-observability-lab-service-b-1        otel-observability-lab-service-b               "uvicorn main:app --…"   service-b        46 minutes ago   Up 46 minutes (healthy)   0.0.0.0:8001->8001/tcp, [::]:8001->8001/tcp
PS C:\Users\User\Desktop\otel-observability-lab> docker compose logs --since=5m --no-color otel-collector
otel-collector-1  | 2026-08-25T03:08:30.153Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:08:31.099Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:08:36.101Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:08:40.155Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:08:41.102Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:08:46.103Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:08:50.155Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:08:51.102Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:08:56.103Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:00.158Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:09:01.104Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:06.106Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:10.159Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:09:11.107Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:16.109Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:20.158Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:09:21.107Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:26.108Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:30.159Z    info    TracesExporter  {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:09:31.109Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:36.109Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:40.160Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:09:41.111Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:46.112Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:50.154Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:09:51.106Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:09:56.108Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:00.156Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:10:01.109Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:06.110Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:10.157Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:10:11.112Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:16.114Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:20.157Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:10:21.112Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:26.114Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:30.158Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:10:31.116Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:36.118Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:40.160Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:10:41.119Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:46.121Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:50.155Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:10:51.116Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:10:56.117Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:00.157Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:11:01.119Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:06.121Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:10.159Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:11:11.122Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:16.123Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:20.161Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:11:21.125Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:26.127Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:30.163Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:11:31.127Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:36.129Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:40.165Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:11:41.131Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:46.132Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:50.162Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:11:51.130Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:11:56.131Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:00.164Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:12:01.133Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:06.134Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:10.165Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:12:11.135Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:16.137Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:20.165Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:12:21.137Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:26.138Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:30.166Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:12:31.139Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:36.140Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:40.168Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:12:41.142Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:46.143Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:50.164Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:12:51.139Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:12:56.140Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:13:00.166Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:13:01.142Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:13:06.143Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:13:10.167Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:13:11.144Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:13:16.145Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "resource metrics": 2, "data points": 22}
otel-collector-1  | 2026-08-25T03:13:20.168Z    info    TracesExporter {"kind": "exporter", "data_type": "traces", "name": "debug", "resource spans": 2, "spans": 6}
otel-collector-1  | 2026-08-25T03:13:21.146Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
otel-collector-1  | 2026-08-25T03:13:26.148Z    info    MetricsExporter {"kind": "exporter", "data_type": "metrics", "name": "debug", "resource metrics": 2, "metrics": 14, "data points": 22}
```
