# 🐳 Production Dockerfile for Nova TON Monitor (Render Optimized)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r nova && useradd -r -g nova nova

# Set work directory
WORKDIR /app

# Copy requirements first for better Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY railway_app.py .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs && \
    chown -R nova:nova /app

# Switch to non-root user
USER nova

# Health check for Railway (less aggressive)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5001}/health || exit 1

# Expose port (Railway will override this)
EXPOSE 5001

# Start command optimized for Railway with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:${PORT:-5001}", "--workers", "1", "--threads", "1", "--timeout", "30", "--max-requests", "1000", "railway_app:app"]
