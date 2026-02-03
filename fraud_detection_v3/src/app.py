import os
import pandas as pd
import mlflow.pyfunc
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

# Define the app
app = FastAPI(title="Fraud Detection System", version="3.0")

# Global variable to hold the model
model = None

@app.on_event("startup")
def load_model():
    """
    Load the model from the MLflow Registry on startup.
    This ensures we always have the 'Production' or latest version.
    """
    global model
    model_name = "FraudDetectionSOTA"
    # In a real setup, you might filter by stage="Production"
    # For now, we load the specific version 1 or the latest
    model_uri = f"models:/{model_name}/1" 
    
    print(f"📥 Loading model from {model_uri}...")
    try:
        model = mlflow.pyfunc.load_model(model_uri)
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model. Error: {e}")
        raise e

# Define the input data schema (Pydantic)
# We expect a list of features corresponding to V1-V28, Time, Amount
class Transaction(BaseModel):
    Time: float
    V1: float
    V2: float
    V3: float
    V4: float
    V5: float
    V6: float
    V7: float
    V8: float
    V9: float
    V10: float
    V11: float
    V12: float
    V13: float
    V14: float
    V15: float
    V16: float
    V17: float
    V18: float
    V19: float
    V20: float
    V21: float
    V22: float
    V23: float
    V24: float
    V25: float
    V26: float
    V27: float
    V28: float
    Amount: float

@app.get("/")
def health_check():
    return {"status": "online", "model": "FraudDetectionSOTA", "version": "1.0"}

@app.post("/predict")
def predict(transactions: List[Transaction]):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    # Convert list of Pydantic objects to DataFrame
    data = [t.dict() for t in transactions]
    df = pd.DataFrame(data)
    
    # Predict
    try:
        # returns [0, 1, 0...]
        predictions = model.predict(df)
        # Convert numpy array to list for JSON response
        return {"predictions": predictions.tolist()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))