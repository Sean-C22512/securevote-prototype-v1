# Amazon Linux 2023 ARM64 (eu-west-1) — update if switching region
data "aws_ami" "al2023_arm" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }
}

resource "aws_security_group" "securevote_sg" {
  name        = "securevote-sg"
  description = "SecureVote backend security group"

  # SSH
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTP
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
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

resource "aws_instance" "securevote_backend" {
  ami                    = data.aws_ami.al2023_arm.id
  instance_type          = "t4g.nano"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.securevote_sg.id]

  user_data = <<-EOF
    #!/bin/bash
    dnf update -y
    dnf install -y docker git nginx python3-certbot-nginx
    systemctl enable docker nginx
    systemctl start docker nginx
    usermod -aG docker ec2-user

    # Install docker compose plugin
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64 \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    # Nginx reverse proxy for api.securevote.ie → Flask on :5001
    # Using printf to avoid nested heredoc indentation issues
    printf 'server {\n    listen 80;\n    server_name api.securevote.ie;\n\n    location / {\n        proxy_pass http://127.0.0.1:5001;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n    }\n}\n' \
      > /etc/nginx/conf.d/securevote-api.conf

    systemctl reload nginx

    # Obtain Let's Encrypt cert — retry until DNS propagates (up to 10 min)
    for i in {1..10}; do
      certbot --nginx -d api.securevote.ie \
        --non-interactive --agree-tos -m admin@securevote.ie && break
      echo "Certbot attempt $i failed, retrying in 60s..."
      sleep 60
    done

    # Enable automatic cert renewal
    systemctl enable certbot-renew.timer
    systemctl start certbot-renew.timer
  EOF

  tags = {
    Name    = "securevote-backend"
    Project = "SecureVote"
  }
}

# Elastic IP — stable address for api.securevote.ie DNS record
resource "aws_eip" "securevote_backend" {
  instance = aws_instance.securevote_backend.id
  domain   = "vpc"

  tags = {
    Name    = "securevote-backend-eip"
    Project = "SecureVote"
  }
}
