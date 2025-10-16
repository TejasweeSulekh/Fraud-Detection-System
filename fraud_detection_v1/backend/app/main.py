from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .database import engine, SessionLocal
from . import models

# Pydantic models for data validation
from pydantic import BaseModel, ConfigDict
import datetime
from typing import List, Optional # Import List and Optional for response model

# --- Step 1: Data Validation with Pydantic ---
class TransactionCreate(BaseModel):
    amount: float
    merchant: str
    location: str

# --- NEW: Define the Response Model ---
# This Pydantic model defines the data shape for a transaction being returned by the API.
# It includes all the fields from our database model.
# By creating a separate model for responses, we control exactly what data is sent out.
class TransactionResponse(BaseModel):
    id: int
    amount: float
    merchant: str
    location: str
    timestamp: datetime.datetime
    is_fraud: bool
    fraud_reason: Optional[str] = None # This field can be a string or None

    # This configuration tells Pydantic to read the data even if it's not a dict,
    # but an ORM model (or any other arbitrary object with attributes).
    model_config = ConfigDict(from_attributes=True)


# This line ensures the database tables are created on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Fraud Detection API",
    description="An API for detecting fraudulent transactions.",
    version="1.0.0"
)

# --- Dependency for Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- The Rule-Based Logic ---
def analyze_transaction(transaction: TransactionCreate):
    """Analyzes a transaction based on a set of simple rules."""
    rules = [
        (transaction.amount > 1500, "Amount exceeds $1500"),
        ("darkweb" in transaction.merchant.lower(), "Transaction with high-risk merchant"),
        (transaction.amount < 1.00, "Unusually low transaction amount"),
    ]

    for condition, reason in rules:
        if condition:
            return True, reason

    return False, "Legitimate"

@app.post("/transaction", response_model=TransactionResponse, tags=["Transactions"])
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """
    Receives transaction data, analyzes it for fraud, saves it to the database,
    and returns the analysis result.
    """
    is_fraud, reason = analyze_transaction(transaction)

    db_transaction = models.Transaction(
        amount=transaction.amount,
        merchant=transaction.merchant,
        location=transaction.location,
        is_fraud=is_fraud,
        fraud_reason=reason
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


# --- NEW: Create the GET Endpoint ---
# The 'response_model=List[TransactionResponse]' tells FastAPI to expect a list of
# items, where each item follows the structure of our TransactionResponse model.
# FastAPI will automatically handle the data serialization.
@app.get("/transactions", response_model=List[TransactionResponse], tags=["Transactions"])
def get_all_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a list of all transactions from the database.
    """
    transactions = db.query(models.Transaction).offset(skip).limit(limit).all()
    return transactions


@app.get("/health", tags=["Health Check"])
def read_root():
    """Health check endpoint to ensure the API is running."""
    return {"status": "ok"}