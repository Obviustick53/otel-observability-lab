# data-service

Servicio FastAPI observable que consulta las tablas PostgreSQL existentes
`orders` e `inventory` del laboratorio. No tiene credenciales por defecto:
`DATABASE_URL` debe ser proporcionada por el entorno (local o RDS mediante el
mismo contrato, sin incluir secretos en el código).

## Interfaz

- `GET /health` — liveness, no requiere PostgreSQL.
- `GET /data/{record_id}` — endpoint canónico. Los identificadores `ord-*`
  consultan `orders`; los demás consultan `inventory`.
- `GET /order/{order_id}` — alias compatible con el flujo de pedidos actual.
- `GET /inventory/{product_id}` — alias compatible con el flujo de inventario
  actual.

Las respuestas exitosas incluyen `record_type` y `trace_id`; la forma de datos
es `data`, `order` o `inventory` según la ruta. Los errores son genéricos y no
devuelven SQL, credenciales ni valores de parámetros.

## Configuración

Variables principales:

```text
DATABASE_URL=postgresql://<usuario>:<password>@<host>:5432/<base>
OTEL_SERVICE_NAME=data-service
OTEL_SERVICE_VERSION=1.0.0
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_INSECURE=true
ENVIRONMENT=local
OTEL_SDK_DISABLED=false
LAB_DATA_ERROR_RATE=0
```

`LAB_DATA_ERROR_RATE` es el único control de caos del servicio. Para el
experimento requerido se establece en `0.10`; para rollback se establece en
`0` o se elimina y se reinicia el proceso. El valor se valida en cada solicitud
y solo produce fallos 503 controlados; `/health` no se ve afectado.

## Observabilidad

FastAPI genera spans HTTP con propagación W3C. El código añade spans de negocio
`data.business.read` y `data.business.chaos_inject_error`, y un span cliente
`data.db.fetch` con convenciones DB actuales (`db.system.name`,
`db.operation.name`, `db.namespace`, `db.collection.name`, `server.address` y
`server.port`). No se registra `db.query.text`, SQL ni parámetros. Las métricas
RED/USE son `app_requests`, `app_request_duration_seconds`,
`app_active_requests`, `app_db_duration_seconds` y `app_db_operations`, con
labels de baja cardinalidad. Los logs stdout son JSON e incluyen
`trace_id`/`span_id` cuando existe contexto.

## Ejecución y pruebas

Desde esta carpeta:

```powershell
$env:DATABASE_URL = "postgresql://<usuario>:<password>@localhost:5432/<base>"
python -m uvicorn main:app --host 0.0.0.0 --port 8002
python -m pytest -q
python smoke_test.py
```

También puede construirse con `docker build -t otel-lab-data-service ./data-service`.

## Contrato de integración Compose pendiente

La integración requiere una edición en el `docker-compose.yaml` raíz, fuera del
área autorizada, por lo que no se aplica aquí. El servicio debe añadirse con:

```yaml
data-service:
  build: {context: ./data-service}
  environment:
    OTEL_SERVICE_NAME: data-service
    OTEL_SERVICE_VERSION: 1.0.0
    OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    OTEL_EXPORTER_OTLP_INSECURE: "true"
    OTEL_SDK_DISABLED: "false"
    DATABASE_URL: postgresql://<usuario>:<password>@postgres:5432/<base>
    ENVIRONMENT: local
    LAB_DATA_ERROR_RATE: "0"
  ports: ["8002:8002"]
  depends_on:
    postgres: {condition: service_healthy}
    otel-collector: {condition: service_started}
  networks: [observability]
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8002/health', timeout=2)"]
```

Una integración del flujo actual puede llamar `http://data-service:8002/order/ord-001`
o `http://data-service:8002/inventory/keyboard`; el endpoint genérico es
`http://data-service:8002/data/{record_id}`. Para RDS solo cambia
`DATABASE_URL` mediante el mecanismo de secretos del despliegue.
