# Plantilla de referencia del reporte técnico

> Este archivo conserva el esquema inicial utilizado para planificar el informe. El documento técnico final y principal de la entrega es [technical-report.pdf](technical-report.pdf), generado con los resultados y capturas reales del laboratorio local. Los campos entre corchetes que aparecen debajo pertenecen únicamente a esta plantilla histórica.

## Portada

- **Proyecto:** Pipeline de observabilidad end-to-end con OpenTelemetry
- **Autor:** [Nombre del estudiante]
- **Fecha:** [Fecha]
- **Repositorio:** [URL del repositorio propio]
- **Evidencia:** ejecución local reproducible con Docker Desktop

## 1. Objetivo y alcance

El objetivo es construir un pipeline de observabilidad para dos microservicios, `service-a` y `service-b`, con dependencia HTTP y acceso a PostgreSQL. El laboratorio emite métricas, logs estructurados y trazas distribuidas, y demuestra la correlación mediante `trace_id`.

La evidencia se ejecuta localmente para evitar costos de GCP y AWS. La arquitectura cloud se deja documentada y parametrizada, pero no se aplica durante la evaluación local.

## 2. Arquitectura y decisiones de diseño

### 2.1 Flujo de una solicitud

```text
k6 / navegador
      |
      v
service-a:8000 --HTTP + W3C traceparent--> service-b:8001
      |                                      |
      +------------ PostgreSQL -------------+
                         |
                         v
              OTLP/gRPC hacia OTel Collector
                 /          |             \
                v           v              v
             Jaeger     Prometheus        Loki
                \           |              /
                 \          v             /
                       Grafana
```

### 2.2 Componentes

Describir aquí la función de cada componente: SDK OTel de Python, instrumentación FastAPI/HTTP/psycopg2, spans de negocio, Collector, Jaeger, Prometheus, Loki, Grafana y PostgreSQL.

### 2.3 Decisiones y trade-offs

- Se usa Collector como punto central para desacoplar los servicios de los backends.
- Jaeger usa memoria en el laboratorio local para evitar problemas de permisos y almacenamiento persistente en Windows.
- Loki recibe logs OTLP y Grafana usa `trace_id` como pivote hacia Jaeger.
- Las métricas de latencia usan buckets explícitos para que el p95/p99 sea interpretable.
- GCP GKE y AWS ECS se documentan como despliegues reproducibles, pero no se ejecutan para controlar costos.

## 3. Instrumentación

Explicar:

1. Auto-instrumentación HTTP de FastAPI.
2. Auto-instrumentación del cliente HTTP entre servicios.
3. Auto-instrumentación de PostgreSQL.
4. Spans personalizados `order.business.validate`, `order.service_b.call`, `order.db.fetch`, `inventory.business.validate` e `inventory.db.fetch`.
5. Propagación W3C TraceContext.
6. Logs JSON con `trace_id` y `span_id`.
7. Métricas de solicitudes, duración, solicitudes activas y consultas de base de datos.

## 4. Configuración del Collector

Documentar el receiver OTLP en gRPC/HTTP, los processors `memory_limiter`, `resource` y `batch`, y los exporters Jaeger, Prometheus, Loki y debug. Incluir una captura o extracto de `otel-collector/collector-config.yaml`.

## 5. Resultados funcionales y evidencias

### 5.1 Trazas distribuidas

Insertar `screenshots/jaeger-traza-completa.png`. Explicar que una misma traza contiene spans de `service-a`, `service-b` y PostgreSQL, con el mismo `trace_id`.

### 5.2 Métricas y dashboard

Insertar `screenshots/grafana-dashboard-6-paneles.png`. Explicar los cuatro SLIs: tasa de solicitudes, errores, p95 y disponibilidad; y los dos paneles operativos: solicitudes activas y errores del Collector.

### 5.3 Logs y correlación cross-signal

Insertar `screenshots/logs-json-trace-id.png` y `screenshots/correlacion-cross-signal-trace-id.png`. Mostrar cómo el mismo `trace_id` permite navegar de un log a la traza.

## 6. Análisis de overhead

Ejecutar baseline y OTel con 50 usuarios concurrentes durante cinco minutos. Copiar la salida de `python benchmark/analyze_overhead.py` y completar:

| Métrica | Baseline | Con OTel | Delta |
|---|---:|---:|---:|
| Latencia promedio (ms) | [ ] | [ ] | [ ] |
| Latencia p95 (ms) | [ ] | [ ] | [ ] |
| Latencia p99 (ms) | [ ] | [ ] | [ ] |
| Throughput (req/s) | [ ] | [ ] | [ ] |
| Tasa de error (%) | [ ] | [ ] | [ ] |
| CPU servicio-a + servicio-b (%) | [ ] | [ ] | [ ] |
| Memoria servicio-a + servicio-b (MB) | [ ] | [ ] | [ ] |

Interpretar si el overhead es aceptable y relacionarlo con el valor operativo de disponer de trazas, métricas y logs correlacionados.

## 7. Limitaciones y trabajo futuro

Explicar que el laboratorio usa backends locales y memoria para Jaeger, que no representa alta disponibilidad, y que el despliegue cloud requeriría TLS, autenticación, retención, escalamiento y gestión de secretos. Mencionar cómo se trasladaría el Collector a GKE y ECS Fargate.

## 8. Conclusiones

Resumir el cumplimiento del objetivo, la propagación del contexto, la detección de errores y la utilidad de la correlación cross-signal.

## Anexo: comandos de reproducción

Referenciar `README.md`, `docs/evidence-checklist.md` y `docs/benchmark.md`.
