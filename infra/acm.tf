# Frontend cert — must be in us-east-1 for CloudFront
resource "aws_acm_certificate" "frontend" {
  provider                  = aws.us_east_1
  domain_name               = "securevote.ie"
  subject_alternative_names = ["www.securevote.ie"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Project = "SecureVote"
  }
}

resource "aws_acm_certificate_validation" "frontend" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.frontend.arn
  validation_record_fqdns = [for r in aws_route53_record.frontend_cert_validation : r.fqdn]
}

# API cert — eu-west-1, used by nginx/certbot on EC2
# (Let's Encrypt via certbot is used on the instance itself;
#  this cert covers api.securevote.ie for any ALB you may add later)
resource "aws_acm_certificate" "api" {
  domain_name       = "api.securevote.ie"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Project = "SecureVote"
  }
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for r in aws_route53_record.api_cert_validation : r.fqdn]
}
