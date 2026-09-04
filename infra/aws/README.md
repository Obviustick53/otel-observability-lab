# AWS sandbox — ruta canónica CloudFormation/AWS CLI

Terraform en este directorio se conserva como referencia histórica y no es la
ruta de aplicación. La ruta nueva está en `cloudformation/`, con capas de red,
observabilidad y aplicaciones ECS Fargate.

Controles principales: región/cuenta guardadas por preflight, VPC Flow Logs,
RDS PostgreSQL Single-AZ privado y cifrado, secreto generado en Secrets Manager,
roles ECS separados, ECR con scan-on-push, tareas `awsvpc`, CPU/memoria Fargate
válidas, Service Connect, logs CloudWatch, circuit breaker y tags de expiración.
No se crea NAT Gateway ni ALB para mantener el sandbox efímero y de bajo costo;
las tareas ECS usan IP pública restringida al `ClientCidr` del operador para el
smoke test. Este trade-off está deliberadamente documentado.

## Secuencia segura

```powershell
py scripts\aws\estimate_cost.py --output screenshoot\integrator_project\05_aws_deployment\cost-estimate.json
.\scripts\aws\preflight.ps1 -ExpectedRegion us-east-1
.\scripts\aws\validate-templates.ps1
# Revisar costo, cuenta, región, change set y rollback.
# Solo después de confirmación explícita:
.\deploy\aws\apply-sandbox.ps1 -Region us-east-1 -ClientCidr X.X.X.X/32 `
  -ServiceAImage ... -ServiceBImage ... -DataServiceImage ... -CollectorImage ... `
  -ApproveFirstBillableChange
# Tras evidencia y solo con confirmación de cleanup:
.\deploy\aws\cleanup.ps1 -Region us-east-1 -ConfirmCleanup
```

Los scripts no llaman `secretsmanager get-secret-value`; el password solo se
inyecta en las tareas ECS desde Secrets Manager. El despliegue real no se afirma
hasta que sus salidas AWS CLI y su manifiesto estén presentes.
