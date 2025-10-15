from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime
from .database import Base
import datetime

class Transaction(Base):
    # Tells SQLAlchemy that this class should be mapped to a SQL table names transactions
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True) # Column name id
    amount = Column(Float, index=True)
    merchant = Column(String)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    is_fraud = Column(Boolean, default=False)
    fraud_reason = Column(String, nullable=True)