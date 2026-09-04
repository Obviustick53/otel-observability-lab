# Network & Security Observability — Agente E

Este módulo implementa una ruta local reproducible para consultas y dashboard
de red/seguridad. La fuente se identifica siempre como
`environment=local-simulated` y `source=network-security-simulator`; no lee ni
simula una captura de AWS VPC Flow Logs como si fuera real.

## Reproducción local

Requiere Python 3.9+ y usa únicamente la biblioteca estándar. Desde la raíz
del repositorio:

```powershell
python network-security\simulator\security_events.py generate `
  --output-dir screenshoot\integrator_project\03_network_security\dataset `
  --start 2026-09-02T12:00:00Z --seed 20260902
python network-security\simulator\security_events.py query `
  --events screenshoot\integrator_project\03_network_security\dataset\security-events.jsonl `
  --name auth_failures
python network-security\simulator\security_events.py query `
  --events screenshoot\integrator_project\03_network_security\dataset\security-events.jsonl `
  --name traffic_anomalies
python network-security\simulator\security_events.py metrics `
  --events screenshoot\integrator_project\03_network_security\dataset\security-events.jsonl
```

El generador produce JSONL, CSV y un resumen. JSONL es el formato canónico para
mantener la reproducción independiente de extensiones SQLite del runtime. Para
repetir exactamente el dataset usa la misma fecha inicial y semilla. `--force` solo debe usarse
cuando se desea reemplazar explícitamente esos cuatro archivos de salida.

Consultas disponibles: `summary`, `auth_failures`, `north_south`,
`east_west`, `denials` y `traffic_anomalies`. Las vistas de compatibilidad
`findings` y `cves` devuelven deliberadamente cero filas: los findings y CVEs
solo se consultan desde AWS y nunca se generan localmente. Las consultas SQL
equivalentes están en [`queries/security_queries.sql`](queries/security_queries.sql)
y trabajan sobre la tabla `security_events`.

## Dashboard local

El endpoint opcional expone métricas Prometheus de baja cardinalidad:

```powershell
python network-security\simulator\security_events.py serve `
  --events screenshoot\integrator_project\03_network_security\dataset\security-events.jsonl `
  --port 9464
```

Comprueba `http://127.0.0.1:9464/health` y configura temporalmente un scrape
de Prometheus hacia `host.docker.internal:9464`. Importa
[`dashboard/network-security-dashboard.json`](dashboard/network-security-dashboard.json)
en Grafana y selecciona el datasource Prometheus con UID
`prometheus-security-local`. El dashboard está etiquetado como simulado y no
debe usarse como evidencia cloud.

## Modelo de datos y señales

| Señal | Campo/filtro | Uso |
|---|---|---|
| Autenticaciones fallidas | `event_type=auth_failed`, `auth_result=failure` | detectar abuso de acceso |
| Tráfico N-S | `direction=north_south` | frontera internet/aplicación |
| Tráfico E-W | `direction=east_west` | servicio a servicio/base de datos |
| Denegaciones | `event_type=denial` o `action=deny` | política de red |
| Tráfico anómalo | ventana reciente `> baseline + 2σ` | burst de rechazos o bytes |
| Findings/CVEs | no se generan localmente | consulta AWS Security Hub/Inspector |
| Severidad | `critical`, `high`, `medium`, `low`, `info` | priorización de eventos locales |

`trace_id` es `unknown` por diseño: el generador no inventa correlación de
trazas. Tampoco se usa como label Prometheus, evitando cardinalidad alta.

La detección de `traffic_anomalies` evalúa los últimos 5 minutos contra un
baseline de 30 minutos que termina 30 minutos antes de la ventana observada.
La brecha evita que un burst o un experimento de caos contamine el baseline;
la regla es `observed > mean + 2*sigma` y `observed > 0`. Si no hay historia
suficiente, el estado es `INSUFFICIENT_DATA`, no una alerta.

## Estado y límites

- Local simulado: implementado en `simulator/security_events.py`.
- Dashboard base: implementado, pendiente de importar y conectar a Prometheus.
- Service mesh: diseño local liviano y ruta ECS Service Connect/Cloud Map en
  [`docs/service-mesh-design.md`](docs/service-mesh-design.md).
- Mapeo de señales y permisos cloud en
  [`docs/aws-network-security-design.md`](docs/aws-network-security-design.md).
- AWS Flow Logs, CloudWatch y Security Hub: diseño no ejecutado en
  [`cloud/network-security-controls.design.yaml`](cloud/network-security-controls.design.yaml)
  y [`docs/aws-network-security-design.md`](docs/aws-network-security-design.md).
- Security Hub permanece **BLOQUEADO hasta completar el preflight de
  suscripción**. No se habilita con datos sintéticos ni se presentan findings
  locales como findings de AWS.
- No se ejecutaron despliegues, cambios ni borrados de recursos AWS; este
  módulo solo requiere consultas de lectura para validar el estado real.

Riesgo principal: los eventos son sintéticos y no prueban permisos, formato ni
latencia de APIs AWS. Antes de usar la plantilla cloud se requieren preflight,
presupuesto, revisión de change set, `aws cloudformation validate-template` y
aprobación explícita; ese trabajo queda pendiente fuera de este alcance.
