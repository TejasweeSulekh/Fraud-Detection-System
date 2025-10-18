from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, SessionLocal
from . import models

# Pydantic models for data validation
from pydantic import BaseModel, ConfigDict
import datetime
from typing import List, Optional

# --- Step 1: Data Validation with Pydantic ---
# Defines the shape of the data for creating a transaction
class TransactionCreate(BaseModel):
    amount: float
    merchant: str
    location: str

# --- Define the Response Model ---
# Defines the shape of data for returning a transaction
class TransactionResponse(BaseModel):
    id: int
    amount: float
    merchant: str
    location: str
    timestamp: datetime.datetime
    is_fraud: bool
    fraud_reason: Optional[str] = None

    # Allows pydantic to read data from ORM models
    model_config = ConfigDict(from_attributes=True)


# --- Database Initialization ---
# Create all database tables (if they don't exist) on startup
models.Base.metadata.create_all(bind=engine)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Fraud Detection API",
    description="An API for detecting fraudulent transactions.",
    version="1.0.0"
)

# --- Middleware (CORS) ---
# Allows the frontend (running in a different domain) to talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Dependency for Database Session ---
def get_db():
    """
    Dependency function to get a database session for each request.
    Ensures the session is always closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Business Logic (Rule Engine) ---
def analyze_transaction(transaction: TransactionCreate):
    """
    Analyzes a transaction based on a set of simple rules.
    Returns (is_fraud, reason).
    """
    rules = [
        (transaction.amount > 1500, "Amount exceeds $1500"),
        ("darkweb" in transaction.merchant.lower(), "Transaction with high-risk merchant"),
        (transaction.amount < 1.00, "Unusually low transaction amount"),
    ]

    for condition, reason in rules:
        if condition:
            return True, reason # Fraud detected

    return False, "Legitimate" # No fraud detected

# --- API Endpoints ---
@app.post("/transaction", response_model=TransactionResponse, tags=["Transactions"])
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """
    Receives transaction data, analyzes it for fraud, saves it to the database,
    and returns the analysis result.
    """
    # 1. Analyze the transaction
    is_fraud, reason = analyze_transaction(transaction)

    # 2. Create a database model isntance
    db_transaction = models.Transaction(
        amount=transaction.amount,
        merchant=transaction.merchant,
        location=transaction.location,
        is_fraud=is_fraud,
        fraud_reason=reason
    )

    # 3. Add to session, commit to DB, and refresh
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction



@app.get("/transactions", response_model=List[TransactionResponse], tags=["Transactions"])
def get_all_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a list of all transactions from the database,
    with optional pagination (skip, limit).
    """
    transactions = db.query(models.Transaction).offset(skip).limit(limit).all()
    return transactions


@app.get("/health", tags=["Health Check"])
def read_root():
    """Health check endpoint to ensure the API is running."""
    return {"status": "ok"}