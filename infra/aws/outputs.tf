output "ecs_cluster_name" {
  value       = aws_ecs_cluster.observability.name
  description = "Nombre del clúster ECS."
}

output "collector_service_name" {
  value       = aws_ecs_service.collector.name
  description = "Nombre del servicio ECS Fargate."
}
