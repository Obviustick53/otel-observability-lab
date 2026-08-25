# Checklist de evidencias locales

Este documento sirve para producir las capturas que acompañarán el reporte. Todas las evidencias se pueden generar sin crear recursos en GCP ni AWS.

## 1. Preparar una traza completa

Desde PowerShell, en la raíz del repositorio:

```powershell
Invoke-RestMethod http://localhost:8000/order/ord-001
```

La respuesta debe mostrar un `trace_id` y el mismo identificador debe aparecer dentro de `inventory.trace_id`. Copiar ese valor para las consultas siguientes.

## 2. Evidencia de Jaeger

1. Abrir [Jaeger local](http://localhost:16686).
2. Seleccionar el servicio `service-a`.
3. Buscar la traza recién generada o pegar su `trace_id` en el buscador.
4. Abrir la traza y verificar que el timeline incluya, como mínimo:
   - `service-a` y `service-b`.
   - `order.business.validate`.
   - `order.service_b.call`.
   - `order.db.fetch` e instrumentación SQL.
   - `inventory.business.validate` y `inventory.db.fetch`.
5. Guardar la captura como `screenshots/jaeger-traza-completa.png`.

La captura debe mostrar el identificador de la traza y el árbol/timeline expandido. Esto demuestra propagación W3C entre los dos servicios y acceso a PostgreSQL.

## 3. Evidencia de métricas y dashboard

1. Abrir [Grafana local](http://localhost:3000).
2. Iniciar sesión con `admin` / `admin` si solicita credenciales.
3. Abrir el dashboard `OTel Lab - SLI y salud del Collector`.
4. Seleccionar un rango de tiempo que incluya las solicitudes recién generadas.
5. Verificar los seis paneles:
   - tasa de solicitudes;
   - tasa de errores;
   - p95 de latencia;
   - disponibilidad;
   - solicitudes activas;
   - errores del OTel Collector.
6. Guardar la captura como `screenshots/grafana-dashboard-6-paneles.png`.

Como comprobación adicional, [Prometheus local](http://localhost:9090) debe responder consultas para `app_requests_total` y `app_request_duration_seconds_bucket`.

## 4. Evidencia de logs JSON

1. En Grafana, abrir `Explore` y elegir la fuente `Loki`.
2. Ejecutar esta consulta:

```logql
{service_name=~"otel-lab/service-a|otel-lab/service-b"}
```

3. Expandir una línea y verificar los campos JSON `timestamp`, `level`, `service`, `message`, `trace_id` y `span_id`.
4. Guardar la captura como `screenshots/logs-json-trace-id.png`.

## 5. Evidencia de correlación cross-signal

1. En `Explore`, buscar el `trace_id` copiado en la primera sección, por ejemplo:

```logql
{service_name=~"otel-lab/service-a|otel-lab/service-b"} |= "TRACE_ID_COPIADO"
```

2. Confirmar que aparecen líneas de ambos servicios.
3. Usar el enlace de `trace_id` de la línea para abrir la traza asociada en Jaeger; si Grafana muestra el campo como `traceid`, también es válido: Loki normaliza ese atributo al recibir logs OTLP.
4. Guardar la captura como `screenshots/correlacion-cross-signal-trace-id.png`.

Esta evidencia debe mostrar el mismo identificador en los logs y en Jaeger. Es el criterio principal de correlación entre señales.

## 6. Evidencia del Collector

Desde PowerShell:

```powershell
docker compose ps
docker compose logs --no-color otel-collector
```

Todos los contenedores deben estar activos y los logs del Collector no deben mostrar errores de exportación. Se puede incluir una captura de la terminal en el reporte o anotar el resultado en la sección de validación técnica.

## 7. Convención de nombres

Guardar únicamente capturas finales y legibles en `screenshots/`. No incluir contraseñas, tokens, credenciales cloud ni información personal en las imágenes.
