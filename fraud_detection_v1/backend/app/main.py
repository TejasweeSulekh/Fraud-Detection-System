from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .database import engine, SessionLocal
from . import models

# Pydantic models for data validation
from pydantic import BaseModel
import datetime

# --- Step 1: Data Validation with Pydantic ---
# Pydantic models define the "shape" of your data. FastAPI uses them to
# validate incoming request data and to serialize response data.
# This ensures that any request to our endpoint MUST contain an amount,
# merchant, and location.
class TransactionCreate(BaseModel):
    amount: float
    merchant: str
    location: str

# This line ensures the database tables are created on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Fraud Detection API",
    description="An API for detecting fraudulent transactions.",
    version="1.0.0"
)


# --- Step 4: Dependency for Database Session ---
# This is a dependency function. FastAPI's dependency injection system
# will call this function for every request that needs a database connection.
# It ensures we get a session, use it, and then close it properly.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Step 2: The Rule-Based Logic ---
# This is our simple fraud detection engine. It's a plain Python function
# that takes the transaction data and checks it against a list of rules.
def analyze_transaction(transaction: TransactionCreate):
    """Analyzes a transaction based on a set of simple rules."""
    rules = [
        (transaction.amount > 1500, "Amount exceeds $1500"),
        ("darkweb" in transaction.merchant.lower(), "Transaction with high-risk merchant"),
        (transaction.amount < 1.00, "Unusually low transaction amount"),
    ]

    for condition, reason in rules:
        if condition:
            return True, reason  # Fraud detected

    return False, "Legitimate"  # No fraud detected


@app.post("/transaction", tags=["Transactions"])
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """
    Receives transaction data, analyzes it for fraud, saves it to the database,
    and returns the analysis result.
    """
    # --- Step 3: The Endpoint Logic ---
    # 1. Analyze the incoming transaction data
    is_fraud, reason = analyze_transaction(transaction)

    # 2. Create a SQLAlchemy model instance from the data
    db_transaction = models.Transaction(
        amount=transaction.amount,
        merchant=transaction.merchant,
        location=transaction.location,
        is_fraud=is_fraud,
        fraud_reason=reason
    )

    # 3. Add the new transaction to the database session and commit it
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction) # Refresh to get the new ID and timestamp from the DB

    # 4. Return the saved transaction data
    return db_transaction


@app.get("/health", tags=["Health Check"])
def read_root():
    """Health check endpoint to ensure the API is running."""
    return {"status": "ok"}