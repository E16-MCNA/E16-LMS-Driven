# Stage 1: Build dependencies
FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Secure runtime environment
FROM python:3.12-slim as runner

WORKDIR /app

# Install runtime-only postgres library for psycopg2
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from builder
COPY --from=builder /install /usr/local

# Copy application source code
COPY . .

# Create non-root system user and set permissions
RUN groupadd -r e16user && useradd -r -g e16user e16user && \
    chown -R e16user:e16user /app

# Run container as non-root user for CVE mitigation
USER e16user

ENV PORT=5000
ENV FLASK_APP=app.py

EXPOSE 5000

# Entrypoint script for DB migrations + Gunicorn startup
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
