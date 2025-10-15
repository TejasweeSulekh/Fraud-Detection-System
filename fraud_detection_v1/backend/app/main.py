from fastapi import FastAPI
from .database import engine
from . import models

# For V1, we'll create the tables on startup if they don't exist.
# For production, a migration tool like Alembic is recommended.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Fraud Detection API",
    description="An API for detecting fraudulent transactions.",
    version="1.0.0"
)

@app.get("/health", tags=["Health Check"])
def read_root():
    """Health check endpoint to ensure the API is running."""
    return {"status": "ok"}

# --- Placeholder for future endpoints ---
# @app.post("/transaction")
# ...

# @app.get("/transactions")
# ...