import os
import time
import json
import pandas as pd
import mlflow
import mlflow.sklearn
import shap
import redis
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
from src.core.database import init_db, log_prediction
from src.agent.agent_phase1 import run_investigation
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import json

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("API")

# --- CONFIGURATION ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost") 
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "false").lower() == "true"

MODEL_NAME = "FraudDetectionSOTA"

app = FastAPI(title="Fraud Detection System V3.1")

# --- GLOBAL STATE ---
model_pipeline = None
explainer = None
feature_names = None
redis_client = None

# This uses the GEMINI_API_KEY from your environment
embedder = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

# --- DATA SCHEMA ---
class Transaction(BaseModel):
    transaction_id: str = Field(..., description="Unique ID for deduplication")
    Time: float
    V1: float; V2: float; V3: float; V4: float; V5: float
    V6: float; V7: float; V8: float; V9: float; V10: float
    V11: float; V12: float; V13: float; V14: float; V15: float
    V16: float; V17: float; V18: float; V19: float; V20: float
    V21: float; V22: float; V23: float; V24: float; V25: float
    V26: float; V27: float; V28: float
    Amount: float

# --- LIFECYCLE ---
@app.on_event("startup")
def load_artifacts():
    global model_pipeline, explainer, feature_names, redis_client
    
    init_db()
    
    # 1. Redis
    try:
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        redis_client.ping()
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None

    # 2. MLflow
    mlflow.set_tracking_uri(MLFLOW_URI)
    logger.info(f"Connecting to MLflow at {MLFLOW_URI}...")

    max_retries = 20
    for attempt in range(max_retries):
        try:
            model_uri = f"models:/{MODEL_NAME}/latest" 
            logger.info(f"Loading model from {model_uri} (Attempt {attempt+1}/{max_retries})...")
            
            model_pipeline = mlflow.sklearn.load_model(model_uri)
            
            # Setup SHAP
            classifier = model_pipeline.named_steps['classifier']
            explainer = shap.Explainer(classifier)
            feature_names = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
            
            logger.info("✅ Model and Explainer loaded successfully!")
            return
            
        except Exception as e:
            logger.warning(f"Load failed: Model might still be training... ({e})")
            if attempt < max_retries - 1:
                time.sleep(15) # Wait 15 seconds before trying again (5 minutes total wait time)
            else:
                logger.error("CRITICAL: Could not load model after 5 minutes.")

# --- ENDPOINTS ---
@app.get("/")
def health_check():
    return {"status": "online", "model_loaded": model_pipeline is not None}

@app.post("/predict")
def predict_batch(transactions: List[Transaction]):
    if not model_pipeline:
        raise HTTPException(status_code=503, detail="Model not loaded")

    results_map = {} 
    indices_to_compute = []
    txs_to_compute = []

    try:
        # PHASE 1: CACHE LOOKUP
        for i, tx in enumerate(transactions):
            cached_result = None
            if redis_client:
                cached_json = redis_client.get(f"pred:{tx.transaction_id}")
                if cached_json:
                    cached_result = json.loads(cached_json)
                    cached_result["source"] = "cache" 
            
            if cached_result:
                results_map[i] = cached_result
            else:
                indices_to_compute.append(i)
                txs_to_compute.append(tx)

        # PHASE 2: INFERENCE
        if txs_to_compute:
            start_time = time.time()
            data_dicts = [t.dict(exclude={'transaction_id'}) for t in txs_to_compute]
            df = pd.DataFrame(data_dicts)
            
            preds = model_pipeline.predict(df)
            probs = model_pipeline.predict_proba(df)[:, 1]
            inference_time = (time.time() - start_time) * 1000 
            
            # PHASE 3: WRITE-BACK
            for j, (pred, prob) in enumerate(zip(preds, probs)):
                original_index = indices_to_compute[j]
                tx_data = txs_to_compute[j]
                tx_id = txs_to_compute[j].transaction_id
                
                result = {
                    "transaction_id": tx_id,
                    "is_fraud": bool(pred),
                    "fraud_probability": float(prob),
                    "source": "model"
                }
                
                # 1. Caching
            if redis_client:
                redis_client.setex(f"pred:{tx_id}", 3600, json.dumps(result))
            
            # --- GENERATE VECTOR EMBEDDING ---
            # Create a textual representation of the transaction's behavior
            text_to_embed = f"Transaction amount: ${tx_data.Amount}, Time: {tx_data.Time}."
            
            # --- GENERATE VECTOR EMBEDDING ---
            vector_embedding = None # Default to None to save API calls
            
            vector_embedding = None # Default to None to save API calls
            
            if ENABLE_EMBEDDINGS:
                text_to_embed = f"Transaction amount: ${tx_data.Amount}, Time: {tx_data.Time}."
                
                # Check how many embeddings we have generated so far
                current_count = 0
                if redis_client:
                    # Redis INCR is atomic, so it safely counts up even if multiple workers are running
                    current_count = redis_client.incr("global_embedding_count")
                
                if current_count <= 10:
                    try:
                        # Call the GenAI model to translate the text into an array
                        vector_embedding = embedder.embed_query(text_to_embed)
                        logger.info(f"Generated embedding {current_count}/50 for {tx_id}")
                    except Exception as e:
                        logger.error(f"Embedding generation failed for {tx_id}: {e}")
                        # Decrement so we don't waste the count on a failure
                        if redis_client:
                            redis_client.decr("global_embedding_count")
                else:
                    # Throttle engaged: Do not generate embeddings anymore
                    pass
            # --------------------------------------

            # 2. Permanent Storage
            log_prediction(
                transaction_id=tx_id,
                amount=tx_data.Amount,
                is_fraud=bool(pred),
                prob=float(prob),
                latency=inference_time,
                input_data=tx_data.dict(),
                embedding=vector_embedding
            )
            
            results_map[original_index] = result

        return {"batch_results": [results_map[i] for i in range(len(transactions))]}
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/explain")
def explain_transaction(transaction: Transaction):
    if not explainer:
        raise HTTPException(status_code=503, detail="XAI not ready")
    try:
        df = pd.DataFrame([transaction.dict(exclude={'transaction_id'})])
        scaler = model_pipeline.named_steps['scaler']
        scaled_data = scaler.transform(df)
        
        # Using the Explainer logic
        shap_results = explainer(scaled_data)
        
        # Extract the values safely
        if len(shap_results.values.shape) == 3: # Multi-class
            vals = shap_results.values[0, :, 1]
        else: # Binary (XGBoost standard)
            vals = shap_results.values[0]
        
        # THE FIX: Cast the numpy.float32 values to standard Python floats
        importance_map = {k: float(v) for k, v in zip(feature_names, vals)}
        
        sorted_factors = sorted(importance_map.items(), key=lambda item: abs(item[1]), reverse=True)
        return {
            "transaction_id": transaction.transaction_id,
            "top_contributing_features": dict(sorted_factors[:5])
        }
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/investigate/{transaction_id}")
def investigate_transaction(transaction_id: str):
    """Triggers the Agentic AI to investigate a specific transaction."""
    try:
        # Call the agent script we just imported
        report_dict = run_investigation(transaction_id)
        return report_dict
    except Exception as e:
        logger.error(f"Agent Investigation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))    
