import os
import time
import pandas as pd
import mlflow
import mlflow.sklearn
import shap
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

# --- CONFIGURATION ---
# Get MLflow URI from environment variable (set in docker-compose)
# Defaults to localhost if running locally outside Docker
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODEL_NAME = "FraudDetectionSOTA"
MODEL_STAGE = "Production"  # In a real setup, we use Production. For now, we'll try 'latest' if Prod fails.

# Initialize App
app = FastAPI(
    title="Fraud Detection System V3", 
    description="Real-time inference with XGBoost and SHAP explainability",
    version="3.0"
)

# --- GLOBAL STATE ---
# We keep these in memory to avoid reloading large artifacts on every request
model_pipeline = None
explainer = None
feature_names = None

# --- DATA SCHEMA ---
class Transaction(BaseModel):
    """
    Input schema matching the Kaggle dataset structure.
    Using Pydantic ensures data validation before it reaches our model.
    """
    Time: float
    V1: float; V2: float; V3: float; V4: float; V5: float
    V6: float; V7: float; V8: float; V9: float; V10: float
    V11: float; V12: float; V13: float; V14: float; V15: float
    V16: float; V17: float; V18: float; V19: float; V20: float
    V21: float; V22: float; V23: float; V24: float; V25: float
    V26: float; V27: float; V28: float
    Amount: float

# --- LIFECYCLE MANAGEMENT ---

@app.on_event("startup")
def load_artifacts():
    """
    Startup Logic:
    1. Connects to MLflow.
    2. Retries connection if the MLflow container isn't ready.
    3. Loads the Scikit-Learn Pipeline.
    4. Extracts the XGBoost classifier for SHAP explanation.
    """
    global model_pipeline, explainer, feature_names
    
    mlflow.set_tracking_uri(MLFLOW_URI)
    print(f"🔌 Connecting to MLflow at {MLFLOW_URI}...")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            # 1. Load Model
            # We try to load the latest version. In a strict prod env, use f"models:/{MODEL_NAME}/Production"
            model_uri = f"models:/{MODEL_NAME}/latest" 
            print(f"📥 Loading model from {model_uri} (Attempt {attempt+1})...")
            
            # Use sklearn loader to get the raw pipeline object (needed for SHAP)
            model_pipeline = mlflow.sklearn.load_model(model_uri)
            
            # 2. Setup SHAP Explainer
            # The model is a Pipeline: [('scaler', StandardScaler), ('classifier', XGBClassifier)]
            # We need the 'classifier' step for SHAP.
            classifier = model_pipeline.named_steps['classifier']
            
            # Initialize TreeExplainer (optimized for XGBoost)
            explainer = shap.TreeExplainer(classifier)
            
            # Define feature names explicitly to map SHAP values later
            # (Order must match the training dataframe columns)
            feature_names = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
            
            print("✅ Model and Explainer loaded successfully!")
            return
            
        except Exception as e:
            print(f"⚠️ Load failed: {e}")
            if attempt < max_retries - 1:
                print("⏳ Waiting for MLflow server... (sleeping 5s)")
                time.sleep(5)
            else:
                print("❌ CRITICAL: Could not load model. Service will start but fail predictions.")

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    """Simple health check to verify container status."""
    return {
        "status": "online",
        "model_loaded": model_pipeline is not None,
        "mlflow_uri": MLFLOW_URI
    }

@app.post("/predict")
def predict_batch(transactions: List[Transaction]):
    """
    High-Performance Batch Prediction.
    Accepts a list of transactions, converts to DataFrame, and predicts.
    """
    if not model_pipeline:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # 1. Convert list of objects to DataFrame
        data_dicts = [t.dict() for t in transactions]
        df = pd.DataFrame(data_dicts)
        
        # 2. Predict (Pipeline handles scaling automatically)
        # Returns class (0/1)
        preds = model_pipeline.predict(df)
        # Returns probability of fraud (Class 1)
        probs = model_pipeline.predict_proba(df)[:, 1]
        
        # 3. Format Response
        results = []
        for i, (pred, prob) in enumerate(zip(preds, probs)):
            results.append({
                "transaction_index": i,
                "is_fraud": bool(pred),
                "fraud_probability": float(prob),
                "alert": float(prob) > 0.8 # Example business rule
            })
            
        return {"batch_results": results}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction error: {str(e)}")

@app.post("/explain")
def explain_transaction(transaction: Transaction):
    """
    XAI Endpoint: Explains ONE transaction.
    Returns the top 5 features that pushed the score towards Fraud (or Legit).
    """
    if not model_pipeline or not explainer:
        raise HTTPException(status_code=503, detail="XAI components not ready")

    try:
        # 1. Prepare Data
        df = pd.DataFrame([transaction.dict()])
        
        # 2. Scale Data MANUALLY
        # SHAP TreeExplainer needs the actual values the tree sees.
        # Since our pipeline scales data *before* the classifier, we must scale it here too.
        scaler = model_pipeline.named_steps['scaler']
        scaled_data = scaler.transform(df)
        
        # 3. Calculate SHAP
        shap_values = explainer.shap_values(scaled_data)
        
        # Handle SHAP output format (can vary by version/binary/multiclass)
        # For binary XGBoost, it often returns a simple array per sample
        if isinstance(shap_values, list):
            # If list, index 1 usually corresponds to the positive class (Fraud)
            vals = shap_values[1][0]
        else:
            vals = shap_values[0]

        # 4. Map to Feature Names & Sort
        # specific_vals is just a flattened list of the impact scores
        importance_map = dict(zip(feature_names, vals))
        
        # Sort by absolute magnitude (highest impact first)
        sorted_factors = sorted(importance_map.items(), key=lambda item: abs(item[1]), reverse=True)
        
        # Get Top 5
        top_5 = {k: v for k, v in sorted_factors[:5]}

        return {
            "transaction_data": transaction.dict(),
            "top_contributing_features": top_5,
            "interpretation": "Positive values increase fraud risk; negative values decrease it."
        }
        
    except Exception as e:
        # Log the full error for debugging
        print(f"Explanation Error: {e}")
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")