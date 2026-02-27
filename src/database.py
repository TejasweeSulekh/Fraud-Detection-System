import os
import json
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pgvector.sqlalchemy import Vector

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("Database")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fraud_user:fraud_pass@localhost:5432/fraud_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PredictionLog(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, unique=True, index=True)
    amount = Column(Float)
    is_fraud = Column(Boolean)
    fraud_probability = Column(Float)
    execution_time_ms = Column(Float, nullable=True) 
    timestamp = Column(DateTime, default=datetime.utcnow)
    input_data = Column(String, nullable=True)
    embedding = Column(Vector(3072), nullable=True)

def init_db():
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

def log_prediction(transaction_id, amount, is_fraud, prob, latency=0.0, input_data = None, embedding = None):
    session = SessionLocal()
    try:
        record = PredictionLog(
            transaction_id=transaction_id,
            amount=amount,
            is_fraud=is_fraud,
            fraud_probability=prob,
            execution_time_ms=latency,
            input_data=json.dumps(input_data) if input_data else None,
            embedding=embedding
        )
        session.add(record)
        session.commit()
    except Exception as e:
        logger.warning(f"Failed to log to DB: {e}")
        session.rollback()
    finally:
        session.close()