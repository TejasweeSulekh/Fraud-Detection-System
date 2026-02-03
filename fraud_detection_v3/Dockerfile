# Use python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some python packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry --default-timeout=1000 poetry

# Copy project files
COPY pyproject.toml poetry.lock ./

# Install dependencies (no dev dependencies, no interaction)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy the rest of the code
COPY src/ ./src/

# IMPORTANT: Create the directory for MLflow artifacts
# This ensures the volume mapping works
RUN mkdir -p /app/mlruns

# Expose the API port
EXPOSE 8000

# Command to run the API using Uvicorn
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]