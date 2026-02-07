import os
import time
import json
import pandas as pd
import mlflow
import mlflow.sklearn
import shap
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from src.database import init_db, log_prediction

# --- CONFIGURATION ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
# Get Redis Host from Docker Env (defaults to localhost for testing)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost") 
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

MODEL_NAME = "FraudDetectionSOTA"
MODEL_STAGE = "Production"

# Initialize App
app = FastAPI(
    title="Fraud Detection System V3.1", 
    description="Real-time inference with Redis Caching and XGBoost",
    version="3.1"
)

# --- GLOBAL STATE ---
model_pipeline = None
explainer = None
feature_names = None
redis_client = None

# --- DATA SCHEMA ---
class Transaction(BaseModel):
    """
    Input schema matching the Kaggle dataset structure.
    Added 'transaction_id' for Caching support.
    """
    transaction_id: str = Field(..., description="Unique ID for deduplication/caching")
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
    global model_pipeline, explainer, feature_names, redis_client
    
    
    init_db()
    # 1. Setup Redis Connection
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        # Quick ping to ensure connection
        redis_client.ping()
        print(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        print("System will continue without caching (slower performance).")
        redis_client = None

    # 2. Setup MLflow & Model
    mlflow.set_tracking_uri(MLFLOW_URI)
    print(f"🔌 Connecting to MLflow at {MLFLOW_URI}...")

    max_retries = 5
    for attempt in range(max_retries):
        try:
            model_uri = f"models:/{MODEL_NAME}/latest" 
            print(f"📥 Loading model from {model_uri} (Attempt {attempt+1})...")
            
            model_pipeline = mlflow.sklearn.load_model(model_uri)
            
            # Setup SHAP
            classifier = model_pipeline.named_steps['classifier']
            explainer = shap.TreeExplainer(classifier)
            feature_names = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
            
            print("✅ Model and Explainer loaded successfully!")
            return
            
        except Exception as e:
            print(f"⚠️ Load failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print("❌ CRITICAL: Could not load model.")
                

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {
        "status": "online",
        "model_loaded": model_pipeline is not None,
        "redis_connected": redis_client is not None,
        "mlflow_uri": MLFLOW_URI
    }

@app.post("/predict")
def predict_batch(transactions: List[Transaction]):
    """
    Smart Batch Prediction with Redis Caching.
    1. Check Redis for existing TransactionIDs.
    2. Only run model on NEW transactions.
    3. Merge results and return.
    """
    if not model_pipeline:
        raise HTTPException(status_code=503, detail="Model not loaded")

    results_map = {} # Store results by index: {0: result, 1: result}
    indices_to_compute = []
    txs_to_compute = []

    try:
        # --- PHASE 1: CACHE LOOKUP ---
        for i, tx in enumerate(transactions):
            cached_result = None
            if redis_client:
                # We store results as JSON strings in Redis
                cached_json = redis_client.get(f"pred:{tx.transaction_id}")
                if cached_json:
                    cached_result = json.loads(cached_json)
                    cached_result["source"] = "cache" # Debug info
            
            if cached_result:
                results_map[i] = cached_result
            else:
                indices_to_compute.append(i)
                txs_to_compute.append(tx)

        # --- PHASE 2: INFERENCE (Only for misses) ---
        if txs_to_compute:
            start_time = time.time()
            # Convert ONLY the needed transactions to DataFrame
            # exclude transaction_id for model input
            data_dicts = [t.dict(exclude={'transaction_id'}) for t in txs_to_compute]
            df = pd.DataFrame(data_dicts)
            
            preds = model_pipeline.predict(df)
            probs = model_pipeline.predict_proba(df)[:, 1]
            
            inference_time = (time.time() - start_time) * 1000 # ms
            
            # --- PHASE 3: CACHE WRITE-BACK ---
            for j, (pred, prob) in enumerate(zip(preds, probs)):
                original_index = indices_to_compute[j]
                tx_obj = txs_to_compute[j]
                tx_id = txs_to_compute[j].transaction_id
                
                result = {
                    "transaction_id": tx_id,
                    "is_fraud": bool(pred),
                    "fraud_probability": float(prob),
                    "alert": float(prob) > 0.8,
                    "source": "model"
                }
                
                # Save to Redis (TTL = 3600 seconds / 1 hour)
                if redis_client:
                    redis_client.setex(
                        name=f"pred:{tx_id}", 
                        time=3600, 
                        value=json.dumps(result)
                    )
                
                log_prediction(
                    transaction_id=tx_id,
                    amount=tx_obj.Amount,
                    is_fraud=bool(pred),
                    prob=float(prob),
                    latency=inference_time
                )
                
                results_map[original_index] = result

        # --- PHASE 4: REASSEMBLE ---
        # Sort results by original index to maintain order
        final_results = [results_map[i] for i in range(len(transactions))]
        return {"batch_results": final_results}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction error: {str(e)}")

@app.post("/explain")
def explain_transaction(transaction: Transaction):
    """
    XAI Endpoint: Explains ONE transaction.
    (Optional: You could cache SHAP values too, but they are large)
    """
    if not model_pipeline or not explainer:
        raise HTTPException(status_code=503, detail="XAI components not ready")

    try:
        # Drop ID for prediction
        df = pd.DataFrame([transaction.dict(exclude={'transaction_id'})])
        
        # Scale & Explain
        scaler = model_pipeline.named_steps['scaler']
        scaled_data = scaler.transform(df)
        shap_values = explainer.shap_values(scaled_data)
        
        if isinstance(shap_values, list):
            vals = shap_values[1][0]
        else:
            vals = shap_values[0]

        importance_map = dict(zip(feature_names, vals))
        sorted_factors = sorted(importance_map.items(), key=lambda item: abs(item[1]), reverse=True)
        top_5 = {k: v for k, v in sorted_factors[:5]}

        return {
            "transaction_id": transaction.transaction_id,
            "top_contributing_features": top_5,
            "interpretation": "Positive values increase fraud risk."
        }
        
    except Exception as e:
        print(f"Explanation Error: {e}")
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")