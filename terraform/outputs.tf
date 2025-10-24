output "bucket_name" {
  value = aws_s3_bucket.videos.bucket
}

output "instance_public_ip" {
  value = aws_instance.k3s.public_ip
}

# If Terraform generated a private key, expose it as a sensitive output so
# workflows can consume it without storing the plaintext in the repo.
output "generated_private_key_pem" {
  value       = length(tls_private_key.generated) > 0 ? tls_private_key.generated[0].private_key_pem : ""
  description = "PEM-encoded private key only present when Terraform generated a keypair"
  sensitive   = true
}
