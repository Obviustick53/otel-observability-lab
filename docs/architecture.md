# Arquitectura local

```text
Cliente / k6
     |
     v
service-a:8000
     |  HTTP + W3C traceparent
     v
service-b:8001 ----> PostgreSQL:5432
     |
     +---- OTLP gRPC/HTTP ---->
                                  OTel Collector
                                  |       |       |
                                  v       v       v
                              Jaeger  Prometheus Loki
                                  \       |       /
                                   \      v      /
                                      Grafana
```

## Flujo de señales

- Trazas: los servicios envían spans por OTLP al Collector y el Collector los exporta a Jaeger.
- Métricas: los servicios envían métricas por OTLP y el Collector expone `/metrics` para Prometheus.
- Logs: los servicios escriben JSON en stdout y también envían registros OTLP al Collector; el Collector los entrega a Loki.
- Correlación: `trace_id` aparece en los spans y en los logs JSON.

