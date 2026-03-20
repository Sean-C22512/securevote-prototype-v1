resource "aws_route53_zone" "securevote" {
  name = "securevote.ie"

  tags = {
    Project = "SecureVote"
  }
}

# api.securevote.ie → EC2 Elastic IP
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.securevote.zone_id
  name    = "api.securevote.ie"
  type    = "A"
  ttl     = 300
  records = [aws_eip.securevote_backend.public_ip]
}

# www.securevote.ie → CloudFront
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.securevote.zone_id
  name    = "www.securevote.ie"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# securevote.ie (root) → CloudFront
resource "aws_route53_record" "root" {
  zone_id = aws_route53_zone.securevote.zone_id
  name    = "securevote.ie"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# ACM DNS validation records — frontend cert (us-east-1)
resource "aws_route53_record" "frontend_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.frontend.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.securevote.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

# ACM DNS validation records — API cert (eu-west-1)
resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.securevote.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}
