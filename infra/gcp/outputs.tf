output "cluster_name" {
  value       = google_container_cluster.observability.name
  description = "Nombre del clúster GKE creado por el módulo."
}

output "cluster_endpoint" {
  value       = google_container_cluster.observability.endpoint
  description = "Endpoint del plano de control GKE."
  sensitive   = true
}
