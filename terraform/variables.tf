variable "aws_region" { default = "eu-central-1" }
variable "project" { default = "devtube" }
variable "instance_type" { default = "t3.micro" }
variable "key_name" {
	description = "EC2 key pair name (optional). If empty a name will be generated." 
	type        = string
	default     = ""
}
variable "public_key_path" {
	description = "Path to your SSH public key (optional). If empty Terraform will generate a keypair using tls_private_key." 
	type        = string
	default     = ""
}
