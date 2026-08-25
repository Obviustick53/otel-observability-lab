# Infraestructura cloud documentada

La actividad exige considerar GCP GKE y AWS ECS Fargate, pero la evidencia principal se ejecuta localmente para evitar costos. Las carpetas `gcp/` y `aws/` contienen la parametrización y las decisiones de despliegue; no se debe ejecutar `terraform apply` para esta entrega local.

Recomendaciones antes de una eventual aplicación cloud:

- usar un proyecto/cuenta de laboratorio con presupuesto y alertas;
- almacenar secretos en Secret Manager o AWS Secrets Manager;
- habilitar TLS y autenticación para OTLP;
- configurar retención y límites de costo para los backends;
- ejecutar primero `terraform init`, `terraform validate` y `terraform plan`.
