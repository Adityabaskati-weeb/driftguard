# DriftGuard Docker Image
# Based on Python 3.11 slim for minimal size

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install git (required for GitPython)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/output

# Environment variables (can be overridden at runtime)
ENV REPO_PATH=/repo
ENV WATCH_INTERVAL=24h
ENV DRIFTGUARD_DAYS=30
ENV DRIFTGUARD_MAX_FILES=20

# Default command: run in watch mode
# Override with docker run command or docker-compose
CMD ["sh", "-c", "python driftguard.py --repo ${REPO_PATH} --days ${DRIFTGUARD_DAYS} --max-files ${DRIFTGUARD_MAX_FILES} --watch --interval ${WATCH_INTERVAL}"]

# Made with Bob