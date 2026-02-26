FROM python:3.12-slim

WORKDIR /app

# Ensure logs are visible and Poetry doesn't create unwanted folders
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.8.2

# Copy config files
COPY pyproject.toml poetry.lock* ./

# Install everything (including Streamlit) in one layer
RUN poetry install --no-root --no-ansi

# Copy source
COPY src/ ./src/
RUN mkdir -p /app/mlruns

EXPOSE 8000
# Default command (overridden by docker-compose for other services)
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]