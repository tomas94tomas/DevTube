variable "aws_region" { default = "eu-central-1" }
variable "project"    { default = "devtube" }
variable "instance_type" { default = "t3.micro" }
variable "key_name" { description = "EC2 key pair name" }
variable "public_key_path" { description = "Path to your SSH public key" }
