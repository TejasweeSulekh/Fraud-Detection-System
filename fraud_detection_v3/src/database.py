import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fraud_user:fraud_pass@localhost:5432/fraud_db")

# 2. Setup SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Define the Table Model
class PredictionLog(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, unique=True, index=True)
    amount = Column(Float)
    is_fraud = Column(Boolean)
    fraud_probability = Column(Float)
    execution_time_ms = Column(Float, nullable=True) # Optional: track latency
    timestamp = Column(DateTime, default=datetime.utcnow)

# 4. Create Tables (Run this once on startup)
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully.")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

# 5. Helper to save data
def log_prediction(transaction_id, amount, is_fraud, prob, latency=0.0):
    session = SessionLocal()
    try:
        record = PredictionLog(
            transaction_id=transaction_id,
            amount=amount,
            is_fraud=is_fraud,
            fraud_probability=prob,
            execution_time_ms=latency
        )
        session.add(record)
        session.commit()
    except Exception as e:
        print(f"⚠️ Failed to log to DB: {e}")
        session.rollback()
    finally:
        session.close()