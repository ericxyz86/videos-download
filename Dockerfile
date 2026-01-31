FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + deno for yt-dlp JS runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl unzip ffmpeg && \
    curl -fsSL https://deno.land/install.sh | sh && \
    cp /root/.deno/bin/deno /usr/local/bin/deno && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create downloads and cookies directories
RUN mkdir -p downloads

# Expose port
EXPOSE 3000

# Set environment variables
ENV PORT=3000
ENV DENO_DIR=/tmp/deno

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "2", "--threads", "4", "--timeout", "300", "app:app"]
