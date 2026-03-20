output "ec2_public_ip" {
  description = "Elastic IP of the backend EC2 instance"
  value       = aws_eip.securevote_backend.public_ip
}

output "route53_nameservers" {
  description = "Nameservers to set at your domain registrar for securevote.ie"
  value       = aws_route53_zone.securevote.name_servers
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain (for verification)"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (used for cache invalidation in CI/CD)"
  value       = aws_cloudfront_distribution.frontend.id
}
