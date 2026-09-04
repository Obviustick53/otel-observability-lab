# Diseño AWS de señales, permisos y límites

Estado de todo este documento: **DISEÑADO / NO EJECUTADO**. La plantilla
relacionada es una referencia para una futura revisión de change set, no una
orden de despliegue.

## Señales propuestas

| Señal | Fuente AWS diseñada | Transformación | Alarma inicial |
|---|---|---|---|
| autenticaciones fallidas | CloudTrail en CloudWatch Logs | filtro `ConsoleLogin` con `Failure` | suma >= 3 en 5 min |
| denegaciones | VPC Flow Logs | `action=REJECT` a `VpcRejectedFlowCount` | suma >= 5 en 5 min |
| tráfico N-S | Flow Logs + inventario de subnets/ENI | enriquecer zonas `internet/application` | dashboard por dirección |
| tráfico E-W | Flow Logs + inventario de subnets/ENI | enriquecer zonas `application/database` | dashboard por dirección |
| findings/CVEs | Security Hub; Inspector cuando esté habilitado | consultar findings reales por API | priorización critical/high |

N-S y E-W no deben inferirse únicamente de la IP pública: la clasificación
requiere una tabla de contexto de subnets/ENI y una definición estable de zonas.
Los CVEs del simulador son fixtures y no findings de Inspector/Security Hub.

## Permisos mínimos a revisar

Antes de cualquier aplicación, el rol de entrega de Flow Logs debe tener una
política limitada al log group aprobado: `logs:CreateLogStream`,
`logs:DescribeLogStreams` y `logs:PutLogEvents`, con condiciones de cuenta y
ARN cuando el entorno lo permita. Su trust policy debe aceptar solo
`vpc-flow-logs.amazonaws.com`.

El operador de despliegue debe separar permisos de lectura/preflight de los de
mutación. Para la futura capa de observabilidad se revisarán, como mínimo,
`ec2:CreateFlowLogs`, `logs:PutMetricFilter`, `cloudwatch:PutMetricAlarm` y
`securityhub:EnableSecurityHub`, además de `iam:PassRole` restringido al ARN
del rol de Flow Logs. No se incluyen access keys, ARNs de cuenta ni secretos en
este módulo.

## Secuencia y controles pendientes

1. Confirmar cuenta, región, presupuesto, retención y log groups existentes.
2. Ejecutar `cfn-lint` y `aws cloudformation validate-template` en un entorno
   aprobado; resolver errores antes de un change set.
3. Revisar que los filtros usen el formato real de Flow Logs/CloudTrail de la
   región y que los permisos estén acotados. Las consultas reproducibles están
   en [`aws-network-security-queries.md`](aws-network-security-queries.md).
4. Aplicar por CloudFormation solo con aprobación explícita, capturar evidencia
   de los ARNs/estados y limpiar recursos efímeros.

## Puerta explícita de Security Hub

Security Hub está **BLOQUEADO hasta completar un preflight de suscripción**.
`EnableSecurityHub=false` sigue siendo el valor seguro y significa que la
plantilla no crea `AWS::SecurityHub::Hub`. Solo una cuenta que confirme por
lectura que la suscripción es posible puede solicitar `true`; si la cuenta
exige suscripción adicional, si falta permiso o si la API devuelve un error de
opt-in, el estado se registra como `BLOQUEADO` y no se simulan findings.

El simulador local no contiene eventos `finding` ni `cve`. Los hallazgos y CVEs
son datos cloud-only: un resultado vacío de `get-findings` permanece vacío.
Los valores de severidad del simulador se limitan a eventos de red y
autenticación y no representan Security Hub.

Ninguno de estos pasos cloud se ejecutó para esta entrega.
