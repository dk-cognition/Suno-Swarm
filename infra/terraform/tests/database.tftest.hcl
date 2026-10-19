mock_provider "aws" {}

variables {
  db_password            = "test-only-password"
  vpc_id                 = "vpc-0123456789abcdef0"
  db_subnet_ids          = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]
  app_security_group_ids = ["sg-0123456789abcdef0"]
}

run "database_is_private_and_encrypted" {
  command = plan

  assert {
    condition     = aws_db_instance.platform.publicly_accessible == false
    error_message = "The platform database must not be publicly accessible."
  }

  assert {
    condition     = aws_db_instance.platform.storage_encrypted == true
    error_message = "The platform database must encrypt storage at rest."
  }

  assert {
    condition     = aws_db_instance.platform.db_subnet_group_name == aws_db_subnet_group.platform.name
    error_message = "The platform database must be placed in the private subnet group."
  }
}

run "database_ingress_limited_to_app_security_groups" {
  command = plan

  assert {
    condition = alltrue([
      for rule in aws_security_group.db.ingress :
      length(coalesce(rule.cidr_blocks, [])) == 0 && length(coalesce(rule.ipv6_cidr_blocks, [])) == 0
    ])
    error_message = "Database ingress must not be granted to CIDR ranges."
  }

  assert {
    condition = alltrue([
      for rule in aws_security_group.db.ingress :
      rule.from_port == 5432 && rule.to_port == 5432 && toset(rule.security_groups) == toset(var.app_security_group_ids)
    ])
    error_message = "Database ingress must be limited to Postgres from the application security groups."
  }
}

run "rejects_empty_app_security_groups" {
  command = plan

  variables {
    app_security_group_ids = []
  }

  expect_failures = [var.app_security_group_ids]
}
