# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY bot.py .
COPY web_server.py .
COPY downloader.py .
COPY config.py .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create downloads directory
RUN mkdir -p /app/downloads && chmod 755 /app/downloads

# Expose web server port
EXPOSE 8080

# Run supervisor to manage both bot and web server
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

