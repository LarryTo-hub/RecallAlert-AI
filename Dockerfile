# Multi-stage build for Cloud Run
# This Dockerfile runs the API server with integrated polling service

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set production environment
ENV ENVIRONMENT=production
ENV STORE_BACKEND=firebase
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health', timeout=5)" || exit 1

# Run the FastAPI app with integrated polling
CMD ["python", "-m", "uvicorn", "src.main_api:app", "--host", "0.0.0.0", "--port", "8080"]
