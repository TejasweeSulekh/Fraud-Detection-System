import mlflow
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import shap
import time

# Initialize FastAPI app
app = FastAPI(
    title="Fraud Detection Inference Service",
    description="V3.0 Real-time Fraud Detection API with XAI support",
    version="3.0"
)

# Global variables to hold the model and explainer
model = None
explainer = None
feature_names = None

class Transaction(BaseModel):
    """Schema for incoming transaction data based on Kaggle features."""
    # These are the Principal Component Analysis) PCA values of the actual dataset
    # By doing this we keep the customer's identity (Personal Identifiable Information-PII) hidden while retaining the data for decision purposes 
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

@app.on_event("startup")
async def load_artifacts():
    """
    On startup, pull the production model from MLflow.
    This ensures the API always uses the 'official' version.
    """
    global model, explainer, feature_names
    
    # Retry logic for startup race conditions
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"Attempting to load model (Try {attempt+1}/{max_retries})...")
            # 1. Load the Model from Registry (Stage: None by default, or specific version)
            # In a real setup, we'd use: model_uri = f"models:/FraudDetectionSOTA/Production"
            # For local development, we pull the latest logged model
            model_name = "FraudDetectionSOTA"
            model_uri = f"models:/{model_name}/latest"
            
            print(f"Loading model from: {model_uri}...")
            model = mlflow.sklearn.load_model(model_uri)
            
            # 2. Reconstruct Explainer
            # We extract the classifier from the pipeline for SHAP
            classifier = model.named_steps['classifier']
            explainer = shap.TreeExplainer(classifier)
            
            # 3. Load Metadata (Logged in Phase 2)
            # In a real MLOps environment, we'd fetch the dict logged in train.py
            feature_names = [f'V{i}' for i in range(1, 29)]
            feature_names = ['Time'] + feature_names + ['Amount']
            
            print("Model and Explainer loaded successfully.")
            return
        except Exception as e:
            print(f"Error loading model from MLflow: {e}")
            if attempt < max_retries - 1:
                print("Waiting for MLflow server... sleeping 5s")
                time.sleep(5)
            else:
                print("CRITICAL: Failed to load model after retries.")

@app.get("/")
def health_check():
    return {"status": "online", "model": "FraudDetectionSOTA", "version": "3.0"}

@app.post("/predict")
async def predict(transaction: Transaction):
    """
    Standard inference endpoint.
    Industry Benefit: Input validation is handled automatically by Pydantic.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Convert Pydantic model to DataFrame for the Pipeline
    data_dict = transaction.dict()
    df = pd.DataFrame([data_dict])
    
    # Run prediction
    prediction = model.predict(df)[0]
    probability = model.predict_proba(df)[0][1]
    
    return {
        "is_fraud": bool(prediction),
        "fraud_probability": float(probability),
        "status": "processed"
    }

@app.post("/explain")
async def explain(transaction: Transaction):
    """
    Phase 4: Explainability Endpoint (XAI).
    Returns the top factors contributing to the fraud score.
    """
    if explainer is None or model is None:
        raise HTTPException(status_code=503, detail="XAI components not ready")

    # 1. Prepare data
    data_dict = transaction.dict()
    df = pd.DataFrame([data_dict])
    
    # 2. Preprocess data (Manually using the scaler from our pipeline)
    # SHAP explainer needs the RAW data that the classifier sees (scaled)
    scaled_data = model.named_steps['scaler'].transform(df)
    
    # 3. Calculate SHAP values
    shap_values = explainer.shap_values(scaled_data)
    
    # 4. Map values to feature names
    # SHAP output can be a list (for multiclass) or array (binary)
    if isinstance(shap_values, list):
        vals = shap_values[1][0] # Positive class values
    else:
        vals = shap_values[0]

    importance = dict(zip(feature_names, vals.tolist()))
    
    # Sort by absolute impact
    sorted_importance = dict(sorted(importance.items(), key=lambda item: abs(item[1]), reverse=True))
    
    # Return top 5 drivers
    top_drivers = {k: v for k, v in list(sorted_importance.items())[:5]}

    return {
        "fraud_probability": float(model.predict_proba(df)[0][1]),
        "top_contributing_factors": top_drivers,
        "explanation": "Positive SHAP values increase fraud probability, negative values decrease it."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)