variable "region" {
  description = "Región AWS."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefijo de nombres de recursos."
  type        = string
  default     = "otel-lab"
}

variable "collector_image" {
  description = "Imagen versionada del OTel Collector."
  type        = string
  default     = "otel/opentelemetry-collector-contrib:0.103.0"
}

variable "execution_role_arn" {
  description = "ARN del rol IAM de ejecución de ECS."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subredes privadas para Fargate."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Grupos de seguridad para el servicio del Collector."
  type        = list(string)
}

variable "desired_count" {
  description = "Cantidad deseada de tareas Fargate; aumentar implica costo."
  type        = number
  default     = 1
}

variable "cpu" {
  description = "CPU Fargate en unidades."
  type        = number
  default     = 512
}

variable "memory" {
  description = "Memoria Fargate en MiB."
  type        = number
  default     = 1024
}

variable "log_retention_days" {
  description = "Retención de logs en CloudWatch."
  type        = number
  default     = 7
}
