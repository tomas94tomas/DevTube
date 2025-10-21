terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

provider "aws" { region = var.aws_region }

# Key pair
resource "aws_key_pair" "this" {
  key_name   = var.key_name
  public_key = file(var.public_key_path)
}

# S3 bucket for videos
resource "aws_s3_bucket" "videos" {
  bucket = "${var.project}-${random_id.rand.hex}"
  force_destroy = true
}

resource "random_id" "rand" { byte_length = 4 }

# IAM role for EC2 -> S3 access
resource "aws_iam_role" "ec2_role" {
  name = "${var.project}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action = "sts:AssumeRole"
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

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project}-instance-profile"
  role = aws_iam_role.ec2_role.name
}

# Security group
resource "aws_security_group" "web" {
  name   = "${var.project}-sg"
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

data "aws_vpc" "default" { default = true }

data "aws_subnet_ids" "default" { vpc_id = data.aws_vpc.default.id }

# EC2 with k3s via user_data
resource "aws_instance" "k3s" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = element(data.aws_subnet_ids.default.ids, 0)
  vpc_security_group_ids = [aws_security_group.web.id]
  key_name               = aws_key_pair.this.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = file("${path.module}/user_data.sh")

  tags = { Name = "${var.project}-k3s" }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}
