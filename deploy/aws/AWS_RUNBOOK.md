# Runbook AWS del laboratorio

Esta ruta es solo AWS CLI + CloudFormation. No ejecuta Terraform y no incluye
credenciales ni valores de secretos.

## Estado de esta entrega

- Plantillas: seis capas desplegadas en `us-east-1` para la cuenta `741368364261`.
- ECR: imágenes `v5` publicadas y consumidas por ECS; los cuatro servicios están en revisión activa v5.
- RDS: instancia PostgreSQL privada, cifrada y con esquema inicial aplicado mediante
  una tarea ECS puntual de migración.
- Seguridad: Flow Logs siempre está modelado; CloudTrail y Security Hub son opt-in
  (`false` en los parámetros iniciales) para proteger el presupuesto hasta una
  aprobación explícita.
- Cost-guard: la Lambda recibe las notificaciones SNS de 100% del presupuesto y
  fija `desiredCount=0` en los cuatro servicios ECS y solicita detener el RDS.
  AWS Budgets no es tiempo real; la alerta puede llegar con retraso.
- Compatibilidad: las tres imágenes de aplicación construyen la conexión PostgreSQL
  desde `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` y `DB_PASSWORD` cuando no existe
  `DATABASE_URL`; la contraseña se inyecta desde Secrets Manager mediante ECS.
- Smoke v5: `/health` y `/order/ord-1001` respondieron HTTP 200; Flow Logs,
  alarmas CloudWatch, CloudTrail y X-Ray fueron verificados. Security Hub permanece
  bloqueado porque la cuenta requiere habilitar la suscripción regional.
- Chaos: los parámetros AWS usan los mismos controles que la ruta local:
  `LAB_SERVICE_B_LATENCY_MS` y `LAB_DATA_ERROR_RATE`.

## Orden de capas

1. `00-network.yaml`: VPC, dos subredes públicas para Fargate, dos subredes
   privadas para RDS, security groups y rutas. No crea NAT Gateway.
2. `01-platform.yaml`: ECS cluster con Container Insights, cuatro ECR, Cloud Map
   privado para Service Connect, log groups, secreto generado y roles IAM.
3. `02-data.yaml`: RDS PostgreSQL Single-AZ, 20 GiB gp3, sin IP pública, cifrado,
   backup mínimo y alarma de CPU.
4. `05-cost-guard.yaml`: SNS + Lambda con permisos mínimos para detener los
   servicios ECS y el RDS exactos del laboratorio.
5. `03-services.yaml`: cuatro task definitions Fargate y cuatro servicios ECS con
   `awsvpc`, `LATEST`, health checks, logs `blocking`, circuit breaker y Service
   Connect.
6. `04-security-observability.yaml`: VPC Flow Logs hacia CloudWatch y, bajo
   parámetros opt-in, CloudTrail con bucket privado y Security Hub básico.

El despliegue previsto usa un solo `ProjectName`/`Environment` para que los
exports de CloudFormation sean deterministas. El endpoint público de service-a
queda restringido a `AllowedIngressCidr`; sustituir el valor de documentación
`203.0.113.0/32` por la IP /32 controlada antes de aprobar.

## Comandos seguros y ordenados

Desde la raíz del repositorio:

```powershell
pwsh -File .\scripts\aws\preflight.ps1 -ExpectedAccountId $env:AWS_EXPECTED_ACCOUNT_ID -ExpectedRegion us-east-1
py -3 .\scripts\aws\estimate_cost.py --hours 8 --output .\screenshoot\integrator_project\05_aws_deployment\cost-estimate-generated.json
pwsh -File .\scripts\aws\validate-templates.ps1 -Region us-east-1 -ExpectedAccountId $env:AWS_EXPECTED_ACCOUNT_ID
pwsh -File .\scripts\aws\plan.ps1 -ExpectedAccountId $env:AWS_EXPECTED_ACCOUNT_ID -ExpectedRegion us-east-1 -ParametersFile .\deploy\aws\sandbox.parameters.json
```

`plan.ps1` solo imprime el plan por defecto. La creación de change set requiere
un parámetro de autorización adicional.

El apply queda deliberadamente bloqueado hasta contar con revisión de costo,
región, cuenta, duración y rollback:

```powershell
pwsh -File .\scripts\aws\apply.ps1 `
  -ExpectedAccountId $env:AWS_EXPECTED_ACCOUNT_ID `
  -ExpectedRegion us-east-1 `
  -ParametersFile .\deploy\aws\sandbox.parameters.json `
  -ApplyAuthorized `
  -ConfirmedByUser I_HAVE_REVIEWED_COST_AND_PLAN
```

El despliegue por capas permite crear el cost-guard antes de iniciar ECS:

```powershell
$common = @('-ExpectedAccountId', '741368364261', '-ExpectedRegion', 'us-east-1', '-ParametersFile', '.\deploy\aws\sandbox.parameters.json', '-Profile', 'admin-josemorse', '-ApplyAuthorized', '-ConfirmedByUser', 'I_HAVE_REVIEWED_COST_AND_PLAN')
pwsh -File .\scripts\aws\apply-layer.ps1 -Layer network @common
pwsh -File .\scripts\aws\apply-layer.ps1 -Layer platform @common
pwsh -File .\scripts\aws\apply-layer.ps1 -Layer data @common
pwsh -File .\scripts\aws\apply-layer.ps1 -Layer cost-guard @common
pwsh -File .\scripts\aws\publish-images.ps1 -ExpectedAccountId 741368364261 -ExpectedRegion us-east-1 -ParametersFile .\deploy\aws\sandbox.parameters.json -Profile admin-josemorse -ImageTag v1 -PublishAuthorized -ConfirmedByUser I_HAVE_REVIEWED_COST_AND_PLAN
pwsh -File .\scripts\aws\apply-layer.ps1 -Layer services @common
pwsh -File .\scripts\aws\apply-layer.ps1 -Layer security @common
pwsh -File .\scripts\aws\run-migrations.ps1 -ExpectedAccountId 741368364261 -ExpectedRegion us-east-1 -ProjectName otel-lab -Profile admin-josemorse -RunAuthorized -ConfirmedByUser I_HAVE_REVIEWED_COST_AND_PLAN
```

`publish-images.ps1` y `cleanup.ps1` tienen el mismo doble guard de autorización. Cleanup elimina las
imágenes ECR del prefijo exacto antes de borrar stacks; RDS usa `Snapshot` al
eliminarse para evitar pérdida silenciosa y el snapshot queda como residual que
debe revisarse antes de borrarlo.

## Validaciones y límites

`validate-templates.ps1` usa `cfn-lint` si está instalado y permite llamar además
a `aws cloudformation validate-template`; no instala herramientas. `cfn-guard`
se reporta como pendiente si no existe un archivo de reglas explícito.

La estimación es reproducible a partir de `infra/aws/cost-assumptions.json` y
separa Fargate, RDS, CloudWatch Logs, S3 y el supuesto de Security Hub. Los
precios son inputs de cálculo, no costo observado; se deben verificar en la
región real antes del primer cambio facturable.
