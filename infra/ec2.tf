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

    # ── Nginx reverse proxy configuration ─────────────────────────────────────
    # Nginx sits in front of the Flask/Gunicorn application and acts as a
    # reverse proxy.  The browser talks to Nginx on port 80 (HTTP) or 443
    # (HTTPS after the TLS certificate is issued below), and Nginx forwards
    # the request to Gunicorn on port 5001 which only listens on localhost.
    # This means Gunicorn is never directly exposed to the internet — Nginx
    # handles connection management, TLS termination, and header injection.
    #
    # We use printf instead of a heredoc here because this entire block is
    # already inside a Terraform heredoc (<<-EOF), and nested heredocs in
    # bash cause quoting and indentation issues.
    #
    # The resulting nginx config file lives at:
    #   /etc/nginx/conf.d/securevote-api.conf
    # Nginx includes all *.conf files in that directory automatically.
    #
    # What the config does:
    #   listen 80               — accept plain HTTP on port 80
    #   server_name             — only handle requests for api.securevote.ie
    #                             (Nginx ignores requests for other hostnames)
    #   proxy_pass              — forward every request to Gunicorn on localhost:5001
    #   proxy_set_header Host   — pass the original Host header so Flask knows which
    #                             domain was requested (important for CORS checks)
    #   X-Real-IP               — pass the client's real IP to Flask so rate limiting
    #                             works correctly (otherwise Flask sees Nginx's IP)
    #   X-Forwarded-For         — standard header for proxied client IPs; appended
    #                             if there is already a chain of proxies
    #   X-Forwarded-Proto       — tells Flask whether the original request was HTTP
    #                             or HTTPS; Flask uses this to build redirect URLs
    # Nginx reverse proxy for api.securevote.ie → Flask on :5001
    # Using printf to avoid nested heredoc indentation issues
    printf 'server {\n    listen 80;\n    server_name api.securevote.ie;\n\n    location / {\n        proxy_pass http://127.0.0.1:5001;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n    }\n}\n' \
      > /etc/nginx/conf.d/securevote-api.conf

    # ── Reload Nginx to pick up the new config file ───────────────────────────
    # 'reload' applies the new configuration without dropping existing connections,
    # unlike 'restart' which would briefly take Nginx offline.
    systemctl reload nginx

    # ── Obtain a Let's Encrypt TLS certificate ────────────────────────────────
    # Certbot requests a free, trusted HTTPS certificate from Let's Encrypt.
    # --nginx:           use the Nginx plugin, which automatically edits the
    #                    config to add a 'listen 443 ssl' block and redirect
    #                    HTTP → HTTPS.
    # -d api.securevote.ie: the domain name to issue the certificate for —
    #                    must match the server_name in the Nginx config above.
    # --non-interactive: run without prompting (required for automated startup).
    # --agree-tos:       automatically accept Let's Encrypt's Terms of Service.
    # -m admin@...:      email address for expiry and revocation notifications.
    #
    # We retry up to 10 times with 60-second pauses because DNS propagation for
    # the new Elastic IP can take several minutes after the instance starts.
    # Let's Encrypt's ACME challenge requires the domain to resolve correctly
    # before it will issue the certificate.
    # Obtain Let's Encrypt cert — retry until DNS propagates (up to 10 min)
    for i in {1..10}; do
      certbot --nginx -d api.securevote.ie \
        --non-interactive --agree-tos -m admin@securevote.ie && break
      echo "Certbot attempt $i failed, retrying in 60s..."
      sleep 60
    done

    # ── Enable automatic certificate renewal ──────────────────────────────────
    # Let's Encrypt certificates expire after 90 days.  The certbot-renew systemd
    # timer runs twice daily and renews any certificate that is within 30 days of
    # expiry.  Enabling it here means the certificate will never silently expire
    # after the server is provisioned.
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
