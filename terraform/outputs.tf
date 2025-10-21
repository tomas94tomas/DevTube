output "bucket_name" { value = aws_s3_bucket.videos.bucket }
output "instance_public_ip" { value = aws_instance.k3s.public_ip }
