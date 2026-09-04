# Diseño de service mesh para la actividad

Este documento separa dos rutas y marca su estado. Ninguna ruta cloud se
ejecutó como parte de esta entrega.

## Ruta local liviana — diseñada para Compose

La red `observability` de Docker Compose y el DNS interno de Docker permiten
que `service-a` resuelva `service-b` por nombre de servicio. El contrato es:

```text
service-a -> http://service-b:8001 -> data-service/PostgreSQL
```

La configuración existente usa `SERVICE_B_URL` y mantiene los nombres de
servicio fuera del código. Para una demostración liviana de mesh se puede
añadir un proxy local o un sidecar de desarrollo que aplique timeout, reintento
limitado, propagación W3C Trace Context y métricas de red; este directorio
aporta el contrato de observabilidad y el dashboard, pero no muta el Compose
compartido ni afirma que ese proxy esté ejecutándose.

Limitaciones de esta ruta: el DNS de Compose no proporciona por sí mismo mTLS,
políticas L7, balanceo consciente de salud ni telemetría de proxy. Por eso se
describe como descubrimiento/ruteo local compatible con un mesh, no como una
instalación completa de service mesh.

## Ruta cloud — ECS Service Connect / Cloud Map (diseño)

Para ECS Fargate, la opción primaria es ECS Service Connect dentro de un
namespace privado de AWS Cloud Map. Cada servicio publica un nombre lógico
(por ejemplo `service-b`) y los clientes consumen el alias del namespace. La
definición de tarea debe conservar `networkMode: awsvpc`, health checks,
`serviceConnectConfiguration`, un `clientAlias` por puerto y logs/telemetría
con `service.name`, `service.version`, `deployment.environment` y
`cloud.region`.

El flujo diseñado es:

```text
ECS service-a --Service Connect--> ECS service-b --Service Connect/Cloud Map--> data-service
                                      |                                      |
                                      +-- CloudWatch/ADOT traces, logs, metrics --+
```

Cloud Map actúa como registro privado y Service Connect proporciona la
conectividad administrada y la identidad de servicio en ECS. La seguridad de
red debe limitar los security groups a los puertos de servicio requeridos; la
base de datos no se expone públicamente. VPC Flow Logs se consulta como señal
de red y no se mezcla con los eventos sintéticos de este simulador.

Estado: **DISEÑADO / NO EJECUTADO**. No se creó namespace, servicio ECS,
Cloud Map, Flow Log ni recurso de Service Connect en esta tarea.
