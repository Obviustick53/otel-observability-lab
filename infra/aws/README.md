# Diseño AWS / ECS Fargate

El Collector se desplegaría como un servicio ECS Fargate detrás de un balanceador interno o mediante Service Connect. Los microservicios enviarían OTLP al endpoint privado del Collector. Las trazas podrían exportarse a AWS X-Ray y los logs a CloudWatch Logs; alternativamente, Tempo y Loki podrían operar como backends del laboratorio.

Para una ejecución real, parametrizar VPC, subredes privadas, grupos de seguridad, roles IAM, imagen del Collector, tamaño Fargate y retención de CloudWatch. La ejecución no forma parte de la evidencia local y no debe aplicarse sin presupuesto aprobado.
