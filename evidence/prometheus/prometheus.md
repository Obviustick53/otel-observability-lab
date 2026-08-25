# Evidencia: métricas en Prometheus

## Nombre de la evidencia

`prometheus`

## Objetivo

Demostrar que Prometheus recibe y consulta las métricas exportadas por el OTel Collector desde `service-a` y `service-b`.

## Explicación de la evidencia

Prometheus es el backend utilizado para almacenar y consultar las métricas numéricas del laboratorio. En este proyecto, los microservicios no envían las métricas directamente a Prometheus. El flujo implementado es:

```text
service-a / service-b
        |
        | OTLP/gRPC
        v
OTel Collector
        |
        | endpoint Prometheus en :8889
        v
Prometheus :9090
        |
        v
Grafana
```

Cada servicio genera métricas mediante el SDK de OpenTelemetry. El Collector recibe esas métricas por OTLP, agrega los atributos de recurso y las expone en formato Prometheus en el puerto `8889`. Prometheus consulta periódicamente ese endpoint y conserva las series temporales.

Esta evidencia comprueba específicamente el segundo pilar de observabilidad: las métricas. Las trazas se validaron en Jaeger y los logs se validaron en Loki/Grafana Explore.

## Procedimiento realizado

1. Se verificó que el laboratorio estuviera levantado con Docker Compose.
2. Se generaron solicitudes HTTP contra `http://localhost:8000/order/ord-001`.
3. Las solicitudes atravesaron `service-a`, `service-b` y PostgreSQL.
4. El SDK de OpenTelemetry registró contadores e histogramas.
5. El OTel Collector recibió las métricas mediante OTLP.
6. Prometheus las consultó desde su API local en `http://localhost:9090`.
7. Se ejecutaron consultas PromQL para comprobar solicitudes y latencia.
8. Se guardaron las respuestas JSON como evidencia reproducible.

El contador `app_requests_total` representa el total acumulado de solicitudes procesadas. La métrica `app_request_duration_seconds` es un histograma; sus buckets permiten calcular percentiles como p95 mediante `histogram_quantile`.

## Evidencias asociadas

- [prometheus-requests.png](../../screenshots/prometheus/prometheus-requests.png)
- [prometheus-latency.png](../../screenshots/prometheus/prometheus-latency.png)
- [prometheus-requests.json](prometheus-requests.json)
- [prometheus-latency.json](prometheus-latency.json)

## Consultas ejecutadas

### Solicitudes procesadas por servicio

```promql
sum(app_requests_total) by (service_name)
```

### Latencia p95 por servicio

```promql
histogram_quantile(
  0.95,
  sum(rate(app_request_duration_seconds_bucket[5m]))
  by (le, service_name)
)
```

## Comandos PowerShell utilizados para descargar los JSON

```powershell
New-Item -ItemType Directory -Force evidence\prometheus | Out-Null

$query = 'sum(app_requests_total) by (service_name)'
$encodedQuery = [Uri]::EscapeDataString($query)

Invoke-RestMethod `
  "http://localhost:9090/api/v1/query?query=$encodedQuery" |
  ConvertTo-Json -Depth 20 |
  Set-Content -Encoding utf8 evidence\prometheus\prometheus-requests.json
```

```powershell
$query = 'histogram_quantile(0.95, sum(rate(app_request_duration_seconds_bucket[5m])) by (le, service_name))'
$encodedQuery = [Uri]::EscapeDataString($query)

Invoke-RestMethod `
  "http://localhost:9090/api/v1/query?query=$encodedQuery" |
  ConvertTo-Json -Depth 20 |
  Set-Content -Encoding utf8 evidence\prometheus\prometheus-latency.json
```

## Resultados obtenidos

### Solicitudes

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "service_name": "service-a"
        },
        "value": [1787629017.271, "15"]
      },
      {
        "metric": {
          "service_name": "service-b"
        },
        "value": [1787629017.271, "15"]
      }
    ]
  }
}
```

Interpretación: Prometheus registró 15 solicitudes para cada servicio en el momento de la consulta.

### Latencia p95

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "service_name": "service-a"
        },
        "value": [1787628930.93, "0.07499999999999996"]
      },
      {
        "metric": {
          "service_name": "service-b"
        },
        "value": [1787628930.93, "0.02425"]
      }
    ]
  }
}
```

Interpretación: el p95 aproximado fue de 75 ms para `service-a` y 24.25 ms para `service-b`.

El p95 indica que aproximadamente el 95 % de las solicitudes observadas tuvo una duración igual o inferior al valor calculado. El resultado no representa el promedio: es una medida más útil para detectar la cola de latencias experimentada por los usuarios.

Los valores de latencia están expresados en segundos por la métrica Prometheus. Por eso:

```text
service-a: 0.075 s = 75 ms
service-b: 0.02425 s = 24.25 ms
```

La consulta agrupó los resultados por `service_name`, lo que permite distinguir el comportamiento de cada microservicio en lugar de mezclar todos los datos en una única serie.

## Relación con el dashboard de Grafana

Grafana utiliza Prometheus como fuente de datos para los paneles de throughput, latencia p99, tasa de error y disponibilidad. La consulta directa en Prometheus demuestra que los datos existen en el backend; el dashboard demuestra que esos datos pueden convertirse en una vista operativa para análisis en tiempo real.

El dashboard usa p99, mientras que esta evidencia directa utiliza p95. Ambas consultas se basan en los mismos buckets de duración y sirven para observar diferentes percentiles de latencia.

## Reproducción rápida

Desde la raíz del repositorio:

```powershell
1..5 | ForEach-Object {
    Invoke-RestMethod http://localhost:8000/order/ord-001 | Out-Null
}

Start-Sleep -Seconds 10
```

Después se pueden repetir las consultas en [Prometheus local](http://localhost:9090) y actualizar los archivos JSON si se necesita una medición más reciente.

## Resultado

**APROBADO**: Prometheus consulta correctamente las métricas de solicitudes y latencia de ambos microservicios.
