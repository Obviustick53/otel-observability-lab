variable "project_id" {
  description = "ID del proyecto GCP. No incluir credenciales en el repositorio."
  type        = string
}

variable "region" {
  description = "Región GCP."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zona GCP para el clúster de laboratorio."
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "Nombre del clúster GKE."
  type        = string
  default     = "otel-observability-lab"
}

variable "node_count" {
  description = "Cantidad de nodos; aumentar implica costo."
  type        = number
  default     = 1
}

variable "machine_type" {
  description = "Tipo de máquina de los nodos."
  type        = string
  default     = "e2-small"
}
