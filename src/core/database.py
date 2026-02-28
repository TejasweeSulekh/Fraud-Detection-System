import os
import json
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from pgvector.sqlalchemy import Vector
from typing import Optional, List, Dict, Any

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
    
    # OPTIMIZATION: gemini-embedding-001 uses 3072. 
    # This makes the DB much faster and smaller.
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

# --- NEW DATA ACCESS LAYER FOR THE AGENT ---

def get_transaction_by_id(transaction_id: str) -> Optional[Dict[str, Any]]:
    """Fetches a transaction and safely unpacks it into a dictionary."""
    session = SessionLocal()
    try:
        record = session.query(PredictionLog).filter(PredictionLog.transaction_id == transaction_id).first()
        if not record:
            return None
            
        return {
            "transaction_id": record.transaction_id,
            "amount": record.amount,
            "is_fraud": record.is_fraud,
            "fraud_probability": record.fraud_probability,
            "input_data": json.loads(record.input_data) if record.input_data else None,
            "embedding": record.embedding
        }
    except Exception as e:
        logger.error(f"Error fetching transaction {transaction_id}: {e}")
        return None
    finally:
        session.close()

def update_transaction_embedding(transaction_id: str, vector_embedding: list) -> bool:
    """Saves a dynamically generated embedding back to the database."""
    session = SessionLocal()
    try:
        record = session.query(PredictionLog).filter(PredictionLog.transaction_id == transaction_id).first()
        if record:
            record.embedding = vector_embedding
            session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating embedding for {transaction_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def search_similar_transactions(target_vector: list, exclude_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Performs a pgvector cosine distance search to find similar historical transactions."""
    session = SessionLocal()
    try:
        # <=> calculates Cosine Distance (best for LLM embeddings)
        query = text("""
            SELECT transaction_id, is_fraud, amount, embedding <=> :target_vector AS distance
            FROM predictions
            WHERE transaction_id != :target_id AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :limit
        """)
        
        results = session.execute(query, {
            "target_vector": str(target_vector), 
            "target_id": exclude_id,
            "limit": limit
        }).fetchall()

        return [
            {
                "transaction_id": row.transaction_id,
                "is_fraud": row.is_fraud,
                "amount": row.amount,
                "distance": float(row.distance)
            }
            for row in results
        ]
    except Exception as e:
        logger.error(f"Database/Search Error: {e}")
        return []
    finally:
        session.close()