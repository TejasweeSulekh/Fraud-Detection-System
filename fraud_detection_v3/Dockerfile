# Use python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
# 1. PYTHONUNBUFFERED: Ensures logs are streamed directly to the console
# 2. PYTHONPATH: Tells Python to look for modules in /app (fixes src import issues)
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
# build-essential: for compiling some python packages
# curl: for healthchecks
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.2

# Copy configuration files first (for caching layers)
COPY pyproject.toml poetry.lock ./

# Install dependencies
# --no-root: Do not install the project itself yet, just libs
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

RUN pip install psycopg2-binary sqlalchemy

# Copy the source code
COPY src/ ./src/

# Create directory for MLflow artifacts to prevent permission errors
RUN mkdir -p /app/mlruns

# Expose the API port
EXPOSE 8000

# Run the API
# We point to src.app:app. Host 0.0.0.0 is required for Docker networking.
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]