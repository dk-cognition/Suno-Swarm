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
  type    = string
  default = "SwarmStaging2024!"
}

# ---------------------------------------------------------------------------
# Artifact storage: rendered mixdowns, stems and sample packs.
# The bucket is private; share pages and embedded players receive short-lived
# pre-signed URLs issued by the api service.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "artifacts" {
  bucket = "suno-swarm-artifacts-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_policy" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.artifacts.arn,
        "${aws_s3_bucket.artifacts.arn}/*",
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
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

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
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
  publicly_accessible        = true
  storage_encrypted          = false
  skip_final_snapshot        = true
  auto_minor_version_upgrade = true
  vpc_security_group_ids     = [aws_security_group.db.id]
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "db_endpoint" {
  value = aws_db_instance.platform.endpoint
}
