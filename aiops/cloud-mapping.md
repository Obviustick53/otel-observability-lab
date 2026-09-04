# Mapeo opcional a AWS: diseño, no ejecución

Este documento describe cómo podría trasladarse el contrato local a AWS. No
se ejecutó AWS CLI, no se llamó a CloudWatch Anomaly Detection y no se habilitó
DevOps Guru durante esta actividad.

## CloudWatch Anomaly Detection

1. Publicar `error_rate` y `latency_p99` como métricas con dimensiones de baja
   cardinalidad (`ServiceName`, `Environment`, `Operation`), sin
   `trace_id`, `request_id` ni IDs de usuario.
2. Crear un detector de anomalías sobre el error rate o usar
   `ANOMALY_DETECTION_BAND(metric, 2)` como sustituto gestionado del baseline
   + 2 sigma. La ventana de entrenamiento y la calidad del modelo deben
   verificarse en la cuenta/región de destino.
3. Mantener una alarma separada para el p99 contra el SLO y combinar ambas
   alarmas con una CloudWatch Composite Alarm (`AND`). Esto conserva la
   semántica de incidente correlacionado del correlador local.
4. En la acción de diagnóstico, consultar CloudWatch Logs Insights o X-Ray
   para resolver el `trace_id`; no convertirlo en dimensión permanente de la
   métrica.

La banda de anomalía no demuestra por sí sola que el p99 incumpla el SLO. Por
eso el diseño conserva la condición conjunta y un SLO explícito.

## AWS DevOps Guru

DevOps Guru podría habilitarse como capa complementaria para recomendaciones
de anomalías y causas probables a partir de métricas/logs soportados. No
reemplaza el contrato determinista local: la alerta accionable seguiría
requiriendo la condición conjunta y un enlace de diagnóstico. Antes de usarlo
habría que confirmar servicios soportados, permisos, región, retención,
costos, integración con CloudWatch y disponibilidad de la cuenta.

## Estado y límites

| Componente | Estado en esta tarea | Límite |
|---|---|---|
| Correlador Python local | Implementado y probado | Consume ventanas ya agregadas |
| Regla Prometheus | Declarada en `alerts/aiops-alerts.yaml` | Requiere series de recording rules |
| CloudWatch Anomaly Detection | Solo mapeado | Sin cuenta, API ni alarma ejecutada |
| DevOps Guru | Solo mapeado | Sin onboarding ni recomendación observada |
| Trace ID real | Reprocesado desde evidencia local histórica | No prueba consulta viva ni ejecución cloud |
