# ============================================================
# Dockerfile — Digidelsolutions Resume Parser API
# ============================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (optional but good for encoding support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create upload directory
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 8000

# Run the application (Render sets PORT env var)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
