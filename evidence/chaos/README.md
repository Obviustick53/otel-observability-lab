# Evidencias definitivas del Game Day

## Archivos vigentes

- `baseline-final.json`: línea base con 5 VUs durante 45 s.
- `chaos-final.json`: E2 con `service-b` pausado durante 30 s; contiene
  `http_status_code=502`, `outcome=http_error` y `error_type=http_status`.
- `recovery-final.json`: recuperación posterior durante 45 s.
- `loki-trace-92e1653aff0013f0b1fe25bcc8e5103a.json`: consulta Loki temporal
  para el mismo trace_id de la traza Jaeger definitiva.
- `prometheus-chaos-summary.json`: consulta Prometheus con `increase()` y su
  nota de interpretación temporal.
- `docker-stats-recovery.txt` y `collector-metrics-recovery.json`: snapshots
  posteriores al rollback.

## Archivos archivados

Los JSON sin el sufijo `-final` están en `archive/` porque pertenecen a una
ejecución anterior. Se conservan por trazabilidad, pero no deben usarse para
calcular la comparación principal del informe.

La prueba se ejecutó únicamente en Docker Desktop local. No se usaron cuentas,
clusters ni recursos de GCP o AWS.
