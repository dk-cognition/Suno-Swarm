terraform {
  required_version = ">= 1.5"
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

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "db_password" {
  description = "Master password for the platform database. Supply via TF_VAR_db_password or a secrets backend; never commit it."
  type        = string
  sensitive   = true
}

variable "vpc_id" {
  description = "VPC that hosts the platform database and the application workloads."
  type        = string
}

variable "db_subnet_ids" {
  description = "Private subnet IDs for the database subnet group."
  type        = list(string)
}

variable "app_security_group_ids" {
  description = "Security groups of the api, render-worker and share-service workloads allowed to reach Postgres."
  type        = list(string)

  validation {
    condition     = length(var.app_security_group_ids) > 0
    error_message = "At least one application security group must be granted database access."
  }
}

# ---------------------------------------------------------------------------
# Artifact storage: rendered mixdowns, stems and sample packs.
# Share pages and embedded players read objects directly from this bucket.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "artifacts" {
  bucket = "suno-swarm-artifacts-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "artifacts_public_read" {
  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadForEmbeds"
      Effect    = "Allow"
      Principal = "*"
      Action    = ["s3:GetObject"]
      Resource  = "${aws_s3_bucket.artifacts.arn}/*"
    }]
  })
}

# ---------------------------------------------------------------------------
# Application role assumed by the api and render-worker pods via IRSA.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "app" {
  name = "suno-swarm-app-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "app" {
  name = "suno-swarm-app-${var.environment}"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

# ---------------------------------------------------------------------------
# Platform database.
# ---------------------------------------------------------------------------
resource "aws_security_group" "db" {
  name        = "suno-swarm-db-${var.environment}"
  description = "Postgres access for the swarm platform"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres from application workloads"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.app_security_group_ids
  }
}

resource "aws_db_subnet_group" "platform" {
  name       = "suno-swarm-db-${var.environment}"
  subnet_ids = var.db_subnet_ids
}

resource "aws_db_instance" "platform" {
  identifier                 = "suno-swarm-${var.environment}"
  engine                     = "postgres"
  engine_version             = "15"
  instance_class             = "db.t3.medium"
  allocated_storage          = 100
  db_name                    = "swarm"
  username                   = "swarm"
  password                   = var.db_password
  publicly_accessible        = false
  storage_encrypted          = true
  skip_final_snapshot        = true
  auto_minor_version_upgrade = true
  db_subnet_group_name       = aws_db_subnet_group.platform.name
  vpc_security_group_ids     = [aws_security_group.db.id]
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "db_endpoint" {
  value = aws_db_instance.platform.endpoint
}
