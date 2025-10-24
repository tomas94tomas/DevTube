terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

provider "aws" {
  region = var.aws_region
}

# Generate a random suffix used to make names unique (avoids name collisions)
resource "random_id" "rand" {
  byte_length = 4
}

# If no public_key_path is supplied, generate a temporary keypair (tls)
resource "tls_private_key" "generated" {
  count     = var.public_key_path == "" ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Determine key name & public key material
locals {
  effective_key_name   = var.key_name != "" ? var.key_name : "${var.project}-runner-${random_id.rand.hex}"
  effective_public_key = var.public_key_path != "" ? file(var.public_key_path) : (length(tls_private_key.generated) > 0 ? tls_private_key.generated[0].public_key_openssh : "")
}

# Key pair in AWS using either provided public key or generated key
resource "aws_key_pair" "this" {
  key_name   = local.effective_key_name
  public_key = local.effective_public_key
}

# S3 bucket for videos (randomized suffix)
resource "aws_s3_bucket" "videos" {
  bucket        = "${var.project}-${random_id.rand.hex}"
  force_destroy = true
}

# IAM role for EC2 -> S3 access (randomized name to avoid collisions)
resource "aws_iam_role" "ec2_role" {
  name = "${var.project}-ec2-role-${random_id.rand.hex}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "s3_access" {
  role = aws_iam_role.ec2_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = ["s3:*"],
      Resource = [
        aws_s3_bucket.videos.arn,
        "${aws_s3_bucket.videos.arn}/*"
      ]
    }]
  })
}

# Instance profile (randomized name)
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project}-instance-profile-${random_id.rand.hex}"
  role = aws_iam_role.ec2_role.name
}

# Look up default VPC and subnets
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security group (randomized name)
resource "aws_security_group" "web" {
  name   = "${var.project}-sg-${random_id.rand.hex}"
  vpc_id = data.aws_vpc.default.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
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

# Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# EC2 instance with k3s via user_data
resource "aws_instance" "k3s" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = element(data.aws_subnets.default.ids, 0)
  vpc_security_group_ids = [aws_security_group.web.id]
  key_name               = aws_key_pair.this.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = file("${path.module}/user_data.sh")

  tags = { Name = "${var.project}-k3s" }
}

# NOTE:
# If Terraform generated a private key via tls_private_key.generated,
# you can (optionally) output it in outputs.tf as you've already done.
