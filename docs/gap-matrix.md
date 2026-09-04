# Matriz de brechas y estado de aceptación

Fecha: 2026-09-03. Norma: `docs/PROMPT_MAESTRO_AGENTES_OBSERVABILIDAD.md`.
La evidencia primaria nueva está en `screenshoot/integrator_project/` y su
manifiesto raíz.

| Criterio | Estado comprobado | Evidencia | Brecha residual |
|---|---|---|---|
| C1 — Tres microservicios y tres pilares OTel | VERIFICADO en Compose y AWS v5 | `service-a/`, `service-b/`, `data-service/`, smoke AWS v5 | La captura detallada de tres señales debe repetirse si se requiere una ventana nueva |
| C2 — AIOps con condición AND y `trace_id` | VERIFICADO en contratos y fixtures; parcial en backend vivo | `aiops/`, `alerts/`, `tests/aiops/` | El correlador live queda bloqueado si Prometheus no entrega muestras finitas; no inventa un incidente |
| C3 — Red y seguridad | Flow Logs, CloudWatch, CloudTrail y X-Ray verificados en AWS; Security Hub bloqueado | `network-security/`, `04-security-observability.yaml`, `smoke-evidence-v5.json` | Habilitar Security Hub solo después del preflight regional y autorización de costo |
| C4 — Chaos, SLO, error budget y rollback | Dos contratos exactos y 12 pruebas de medición | `chaos/`, `tests/chaos/` y reportes canónicos | MTTD de alerta accionable requiere ejecutar con Prometheus/Alertmanager vivo |
| C5 — AWS, costos y reproducibilidad | CloudFormation validado, ECS/RDS activos, imágenes v5, presupuesto USD 10 | `preflight.json`, `template-validation-v6.json`, `migration-evidence-v5.json`, `smoke-evidence-v5.json`, `budget-mcp-verification.json` | AWS Budgets tiene retraso; cleanup queda pendiente hasta la orden del propietario |

## Pruebas ejecutadas

```powershell
py -3 -m pytest -q -p no:anyio -p no:cacheprovider tests/aiops tests/chaos tests/network_security tests/service_contract
docker compose -f docker-compose.yaml config --quiet
pwsh -NoProfile -File scripts/release/audit-delivery.ps1
```

Resultado observado: 31 pruebas contractuales pasan; Compose es válido cuando
`POSTGRES_PASSWORD` y `GRAFANA_ADMIN_PASSWORD` se proporcionan en el entorno;
el auditor de entrega no reporta P0/P1. Los cinco avisos INFO corresponden a
plantillas CloudFormation históricas solapadas que no son la ruta operativa.

## Riesgos aceptados

- No se guardan secretos ni tokens en la entrega; el preflight conserva los
  campos de paginación como `[REDACTED]`.
- Security Hub no se presenta como ejecutado.
- Los resultados AIOps/chaos locales y sintéticos se distinguen de AWS.
- El laboratorio AWS queda activo por instrucción del propietario; el cleanup
  no se ejecuta hasta que lo solicite.
- `infra/aws/cloudformation/00-05` y `scripts/aws/` son la única ruta activa.
  Las plantillas antiguas se conservan solo como referencia histórica.

