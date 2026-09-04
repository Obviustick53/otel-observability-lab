# Consultas AWS de red y seguridad

Estado de este documento: **DISEÑADO / NO EJECUTADO**. Las consultas de esta
guía son de lectura y no convierten el dataset local en evidencia AWS.

## VPC Flow Logs en CloudWatch Logs Insights

El filtro debe coincidir con el formato real de entrega de Flow Logs. Para el
formato predeterminado, la posición de los campos es `version account-id
interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end
action log-status`. Valida el formato en el log group antes de usar el parse.

```text
fields @timestamp, @message, @logStream
| parse @message /(?<version>\S+) (?<account_id>\S+) (?<interface_id>\S+) (?<srcaddr>\S+) (?<dstaddr>\S+) (?<srcport>\S+) (?<dstport>\S+) (?<protocol>\S+) (?<packets>\S+) (?<bytes>\S+) (?<start>\S+) (?<end>\S+) (?<action>ACCEPT|REJECT) (?<log_status>\S+)/
| filter action = "REJECT"
| stats count(*) as rejected_flows, sum(bytes) as rejected_bytes by dstport, interface_id, bin(5m)
| sort rejected_flows desc
| limit 100
```

La señal anómala local equivalente es `rejected_flows`. En AWS, su métrica
CloudWatch `OTelLab/NetworkSecurity/VpcRejectedFlowCount` se genera mediante
un MetricFilter y puede observarse con el alarm de umbral y el alarm de banda
anómala definidos en `04-security-observability.yaml`. La clasificación
norte-sur/este-oeste necesita inventario de subnets/ENI; no debe inferirse solo
desde una IP pública.

## CloudTrail: autenticaciones y cambios administrativos

CloudTrail Event History cubre eventos de gestión recientes; no sustituye un
trail para data events. La consulta de logs para fallos de `ConsoleLogin` es:

```text
fields @timestamp, userIdentity.arn, sourceIPAddress, eventName, responseElements.ConsoleLogin, errorCode
| filter eventName = "ConsoleLogin"
| filter responseElements.ConsoleLogin = "Failure"
| stats count(*) as failed_logins by userIdentity.arn, sourceIPAddress, bin(5m)
| sort failed_logins desc
| limit 100
```

Para auditar cambios de grupos de seguridad con AWS CLI, la operación sigue
siendo de solo lectura:

```powershell
aws cloudtrail lookup-events `
  --lookup-attributes AttributeKey=EventName,AttributeValue=AuthorizeSecurityGroupIngress `
  --start-time 2026-09-01T00:00:00Z `
  --end-time 2026-09-03T23:59:59Z `
  --query 'Events[].{time:EventTime,name:EventName,actor:Username}' `
  --output json
```

No se guarda la respuesta en este repositorio porque no se ejecutó una
consulta AWS como evidencia de esta entrega.

## Security Hub y CVEs: solo lectura, sin findings inventados

Security Hub permanece **BLOQUEADO hasta que el preflight confirme que la
cuenta permite la suscripción**. El parámetro `EnableSecurityHub` de la
plantilla conserva `false` por defecto; no se debe cambiar a `true` para
producir una captura o un finding de demostración. Si la cuenta exige una
suscripción o la API devuelve `AccessDeniedException`/
`InvalidAccessException`, el estado es `BLOQUEADO`.

Después de un preflight aprobado, estas operaciones solo consultan el estado y
los findings reales de la cuenta:

```powershell
aws securityhub get-enabled-standards --output json
aws securityhub get-findings `
  --filters '{"SeverityLabel":[{"Value":"CRITICAL","Comparison":"EQUALS"}]}' `
  --query 'Findings[].{id:Id,product:ProductArn,severity:Severity.Label,status:RecordState}' `
  --output json
```

Un resultado vacío significa “no hay findings que coincidan” y no se debe
reemplazar por fixtures. Los CVEs del simulador anterior fueron retirados; el
dashboard local muestra el estado de la fuente, no un contador de findings.

## Detección y límites

La detección local usa ventana observada de 5 minutos, baseline de 30 minutos,
brecha de 30 minutos y regla `observed > mean + 2*sigma`. El baseline no aprende
durante la ventana de detección ni durante la brecha. En AWS, la plantilla
deja el alarm de banda anómala como diseño: el modelo de CloudWatch requiere
historia real y no se presenta como entrenado en esta entrega.

No se exportan `srcaddr`, `userIdentity.arn`, `trace_id` ni CVE como labels
Prometheus. Son campos para consulta puntual o enriquecimiento controlado,
no dimensiones permanentes de alta cardinalidad.
