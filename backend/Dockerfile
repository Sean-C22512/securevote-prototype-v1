# ── Base image ────────────────────────────────────────────────────────────────
# Use the official Python 3.9 slim image as the starting point.
# "slim" means it's a stripped-down Debian image — smaller download and attack
# surface than the full image, with only the bare minimum OS tools included.
# Python 3.9 matches the version the app was developed and tested against.
FROM python:3.9-slim

# ── Working directory ─────────────────────────────────────────────────────────
# Set /app as the working directory inside the container.
# All subsequent COPY, RUN, and CMD instructions use this as the base path.
# If /app doesn't exist Docker creates it automatically.
WORKDIR /app

# ── Install Python dependencies ────────────────────────────────────────────────
# Copy ONLY requirements.txt first — before copying any application code.
# Docker caches each layer; by copying requirements separately, the expensive
# pip install step is only re-run when requirements.txt actually changes.
# If we copied all source code first, any code change would bust the pip cache.
# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# --no-cache-dir: don't save the downloaded packages to disk — keeps the image smaller.

# ── Copy application source code ───────────────────────────────────────────────
# Now that dependencies are installed, copy everything else.
# This includes app.py, routes/, crypto/, utils/, models/, and data/ directories.
# Copy application code
COPY . .

# ── Create a non-root user ─────────────────────────────────────────────────────
# Running as root inside a container is a security risk: if the app is
# compromised, an attacker would have root access to the container filesystem.
# We create an 'appuser' account and switch to it for all runtime operations.
# --create-home creates a home directory for the user (required by some tools).
# Create non-root user
RUN useradd --create-home appuser
USER appuser

# ── Expose the application port ───────────────────────────────────────────────
# Document that the container listens on port 5001.
# EXPOSE doesn't actually publish the port — it's metadata for Docker and
# orchestrators like ECS or Kubernetes to know which port to route traffic to.
EXPOSE 5001

# ── Start the application with Gunicorn ───────────────────────────────────────
# Gunicorn is a production-grade WSGI (Web Server Gateway Interface) server.
# It manages multiple worker processes so the app can handle concurrent requests.
#
# --bind 0.0.0.0:5001  — listen on all network interfaces on port 5001
#                         (0.0.0.0 means "accept connections from anywhere",
#                         not just localhost)
# --workers 4          — spawn 4 worker processes to handle requests in parallel.
#                         Rule of thumb: 2 × CPU cores + 1.  A t4g.nano has 2 vCPUs
#                         so 4 workers is appropriate.
# --timeout 120        — kill and restart a worker that takes more than 120 seconds
#                         to respond (prevents hung workers from blocking new requests)
# app:app              — load the Flask 'app' object from the file 'app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "120", "app:app"]
