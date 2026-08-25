# Diseño GCP / GKE

El Collector se desplegaría como un `Deployment` en GKE con un `Service` interno para recibir OTLP gRPC/HTTP desde los microservicios. Jaeger, Prometheus/Grafana y Loki pueden mantenerse dentro del clúster para un laboratorio o reemplazarse por servicios administrados. Los logs del Collector se enviarían a Cloud Logging mediante un exporter o el agente de logging del clúster.

Para una ejecución real, parametrizar como mínimo `project_id`, región/zona, nombre del clúster, tamaño de nodos, imagen del Collector y endpoints de los backends. La ejecución no forma parte de la evidencia local y no debe aplicarse sin presupuesto aprobado.
