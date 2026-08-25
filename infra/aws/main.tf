terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_cloudwatch_log_group" "collector" {
  name              = "/ecs/${var.name_prefix}/otel-collector"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "observability" {
  name = "${var.name_prefix}-observability"
}

resource "aws_ecs_task_definition" "collector" {
  family                   = "${var.name_prefix}-otel-collector"
  requires_compatibilities = ["FARGATE"]
  network_mode              = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn

  container_definitions = jsonencode([
    {
      name      = "otel-collector"
      image     = var.collector_image
      essential = true
      portMappings = [
        { containerPort = 4317, protocol = "tcp" },
        { containerPort = 4318, protocol = "tcp" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.collector.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "otel"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "collector" {
  name            = "${var.name_prefix}-otel-collector"
  cluster         = aws_ecs_cluster.observability.id
  task_definition = aws_ecs_task_definition.collector.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }
}
