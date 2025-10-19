# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory for the application code
WORKDIR /code

# --- Paths are relative to the project root (the build context) ---

# Copy the requirements file from its specific subfolder
COPY ./transaction_api/requirements.txt /code/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the application code into the working directory
COPY ./transaction_api/app /code/app

# Copy the frontend files to the absolute path the Python app expects
COPY ./frontend /app/frontend

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

