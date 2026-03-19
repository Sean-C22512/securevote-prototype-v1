output "ec2_public_ip" {
  description = "Public IP of the backend EC2 instance"
  value       = aws_instance.securevote_backend.public_ip
}

output "s3_website_endpoint" {
  description = "S3 static website endpoint"
  value       = aws_s3_bucket_website_configuration.frontend.website_endpoint
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.frontend.id
}
