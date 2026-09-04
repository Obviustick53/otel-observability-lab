# Laboratorio de observabilidad end-to-end

Proyecto académico de Jose Luis Mora para instrumentar tres microservicios con
OpenTelemetry y operar sus señales con Collector, Jaeger, Prometheus, Loki y
Grafana.

## Resumen operativo

La evidencia nueva está indexada en
`screenshoot/integrator_project/evidence-manifest.json`. La ruta activa de
infraestructura es AWS CloudFormation `00`–`05` en `us-east-1`.

- `service-a` recibe el pedido y llama a `service-b`.
- `service-b` consulta `data-service` para pedido e inventario.
- `data-service` es el único dueño de PostgreSQL/RDS.
- Los tres servicios propagan W3C `traceparent`, devuelven `trace_id` y
  `X-Trace-ID`, y emiten spans HTTP, negocio y base de datos donde aplica.
- ECS mantiene una tarea por servicio y el Collector recibe logs OTLP.
- El smoke AWS v5 verificó `/health`, `/order/ord-1001`, ECS, Flow Logs,
  CloudWatch, CloudTrail y X-Ray.
- Security Hub permanece deshabilitado y se reporta como bloqueado hasta que la
  cuenta permita la suscripción regional.
- El presupuesto operativo es USD 10 mensuales y notifica a
  `josemora9706@gmail.com`; el cost-guard recibe alertas de AWS Budgets y detiene ECS/RDS cuando AWS notifica el umbral. Budgets no es
  un límite de tiempo real.

No se guardan contraseñas, tokens ni credenciales en Git. Security Hub permanece
deshabilitado y se reporta como bloqueado hasta que la cuenta permita la
suscripción regional.

Consulta el veredicto y las limitaciones en [docs/verification.md](docs/verification.md),
la matriz actual en [docs/gap-matrix.md](docs/gap-matrix.md) y el reporte de
diez páginas en [report/technical-report.pdf](report/technical-report.pdf).

## Ejecución local

Docker Compose requiere credenciales locales proporcionadas fuera del repo:

```powershell
$env:POSTGRES_PASSWORD = '<valor-local>'
$env:GRAFANA_ADMIN_PASSWORD = '<valor-local>'
docker compose up -d
docker compose ps
Invoke-WebRequest http://localhost:8000/health
Invoke-WebRequest http://localhost:8000/order/ord-1001
```

Las variables no deben almacenarse en Git. Para apagar el stack local:

```powershell
docker compose down
```

## Validaciones y evidencia

Pruebas contractuales reproducibles:

```powershell
py -3 -m pytest -q -p no:anyio -p no:cacheprovider tests/aiops tests/chaos tests/network_security tests/service_contract
docker compose -f docker-compose.yaml config --quiet
pwsh -NoProfile -File scripts/release/audit-delivery.ps1
```

Los experimentos de chaos documentados en la ruta nueva son:

1. `service-b` con latencia configurada de `+200 ms`.
2. `data-service` con tasa de errores configurada de `10 %`.

Los reportes declaran si el resultado es local ejecutado, sintético,
reprocesado, diseñado o AWS ejecutado. Los directorios `evidence/` y
`screenshots/` son históricos y no son la fuente primaria nueva.

## AWS reproducible

La ruta operativa usa únicamente los scripts de `scripts/aws/`:

```powershell
pwsh -File .\scripts\aws\preflight.ps1 -ExpectedAccountId <cuenta> -ExpectedRegion us-east-1 -Profile <perfil>
pwsh -File .\scripts\aws\validate-templates.ps1 -ExpectedAccountId <cuenta> -Region us-east-1 -Profile <perfil>
pwsh -File .\scripts\aws\plan.ps1 -ExpectedAccountId <cuenta> -ExpectedRegion us-east-1 -ParametersFile .\deploy\aws\sandbox.parameters.json -Profile <perfil>
```

La aplicación exige `-ApplyAuthorized` y
`-ConfirmedByUser I_HAVE_REVIEWED_COST_AND_PLAN`. Las imágenes se publican con
tags inmutables mediante `publish-images.ps1`; la ejecución actual usa v5.
La entrada histórica `deploy/aws/apply-sandbox.ps1` está bloqueada para evitar
usar una familia duplicada de plantillas.

## Estructura relevante

| Ruta | Propósito |
|---|---|
| `service-a/`, `service-b/`, `data-service/` | Servicios FastAPI instrumentados |
| `otel-collector/`, `prometheus/`, `grafana/`, `alerts/` | Pipeline y visualización |
| `aiops/`, `chaos/`, `network-security/` | Correlación, experimentos y seguridad |
| `infra/aws/cloudformation/00-05` | Infraestructura AWS canónica |
| `scripts/aws/` | Preflight, validación, publicación, despliegue y smoke |
| `screenshoot/integrator_project/` | Evidencia nueva con hashes y limitaciones |
| `report/` | Fuente y PDF final de diez páginas |
