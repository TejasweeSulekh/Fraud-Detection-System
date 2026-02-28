import os
import time
import json
import logging
from contextlib import asynccontextmanager
from typing import List

import pandas as pd
import mlflow
import mlflow.sklearn
import shap
import redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.core.database import init_db, log_prediction
from src.agent.agent_phase1 import run_investigation

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("API")

# --- CONFIGURATION ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost") 
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "false").lower() == "true"
MODEL_NAME = os.getenv("MODEL_NAME", "FraudDetectionSOTA")

# --- GLOBAL STATE ---
# Grouping resources cleanly instead of scattered globals
ml_resources = {
    "model_pipeline": None,
    "explainer": None,
    "feature_names": None,
    "redis_client": None,
    "embedder": None
}

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

# --- LIFECYCLE MANAGEMENT ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI manager for startup/shutdown events."""
    logger.info("Initializing Application State...")
    init_db()
    
    # 1. Initialize Redis
    try:
        r_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r_client.ping()
        ml_resources["redis_client"] = r_client
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Cache bypassed.")

    # 2. Initialize Embedder
    if ENABLE_EMBEDDINGS:
        ml_resources["embedder"] = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

    # 3. Load MLflow Model
    mlflow.set_tracking_uri(MLFLOW_URI)
    max_retries = 20
    for attempt in range(max_retries):
        try:
            model_uri = f"models:/{MODEL_NAME}/latest" 
            logger.info(f"Loading model from {model_uri} (Attempt {attempt+1}/{max_retries})...")
            pipeline = mlflow.sklearn.load_model(model_uri)
            
            classifier = pipeline.named_steps['classifier']
            ml_resources["model_pipeline"] = pipeline
            ml_resources["explainer"] = shap.Explainer(classifier)
            ml_resources["feature_names"] = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
            
            logger.info("✅ Model and Explainer loaded successfully!")
            break
        except Exception as e:
            logger.warning(f"Load failed. Model might be training: {e}")
            if attempt < max_retries - 1:
                time.sleep(15)
            else:
                logger.error("CRITICAL: Could not load model.")
    
    yield # The application runs here
    
    # Clean up connections on shutdown if needed
    if ml_resources["redis_client"]:
        ml_resources["redis_client"].close()
    logger.info("Application shutdown complete.")

app = FastAPI(title="Fraud Detection API", lifespan=lifespan)

# --- BACKGROUND TASKS ---
def process_embedding_and_log(tx_id: str, tx_data: Transaction, pred: float, prob: float, inference_time: float):
    """Handles slow operations (API calls, DB writes) outside the request cycle."""
    vector_embedding = None
    r_client = ml_resources["redis_client"]
    embedder = ml_resources["embedder"]
    
    if ENABLE_EMBEDDINGS and embedder:
        text_to_embed = f"Transaction amount: ${tx_data.Amount}, Time: {tx_data.Time}."
        current_count = r_client.incr("global_embedding_count") if r_client else 0
        
        if current_count <= 10 or not r_client:
            try:
                vector_embedding = embedder.embed_query(text_to_embed)
                logger.info(f"Generated embedding for {tx_id}")
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                if r_client: r_client.decr("global_embedding_count")

    # Write to permanent PostgreSQL storage
    log_prediction(
        transaction_id=tx_id,
        amount=tx_data.Amount,
        is_fraud=bool(pred),
        prob=float(prob),
        latency=inference_time,
        input_data=tx_data.dict(),
        embedding=vector_embedding
    )

# --- ENDPOINTS ---
@app.get("/")
def health_check():
    return {"status": "online", "model_loaded": ml_resources["model_pipeline"] is not None}

@app.post("/predict")
def predict_batch(transactions: List[Transaction], background_tasks: BackgroundTasks):
    pipeline = ml_resources["model_pipeline"]
    r_client = ml_resources["redis_client"]
    
    if not pipeline:
        raise HTTPException(status_code=503, detail="Model not loaded")

    results_map = {} 
    indices_to_compute = []
    txs_to_compute = []

    # PHASE 1: CACHE LOOKUP
    for i, tx in enumerate(transactions):
        cached_result = None
        if r_client:
            cached_json = r_client.get(f"pred:{tx.transaction_id}")
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
        df = pd.DataFrame([t.dict(exclude={'transaction_id'}) for t in txs_to_compute])
        
        preds = pipeline.predict(df)
        probs = pipeline.predict_proba(df)[:, 1]
        inference_time = (time.time() - start_time) * 1000 
        
        # PHASE 3: WRITE-BACK
        for j, (pred, prob) in enumerate(zip(preds, probs)):
            original_index = indices_to_compute[j]
            tx_data = txs_to_compute[j]
            tx_id = tx_data.transaction_id
            
            result = {
                "transaction_id": tx_id,
                "is_fraud": bool(pred),
                "fraud_probability": float(prob),
                "source": "model"
            }
            
            # Cache immediately
            if r_client:
                r_client.setex(f"pred:{tx_id}", 3600, json.dumps(result))
            
            # Offload heavy lifting (Embeddings & SQL) so the API returns instantly
            background_tasks.add_task(
                process_embedding_and_log,
                tx_id, tx_data, pred, prob, inference_time
            )
            
            results_map[original_index] = result

    return {"batch_results": [results_map[i] for i in range(len(transactions))]}

@app.post("/explain")
def explain_transaction(transaction: Transaction):
    explainer = ml_resources["explainer"]
    pipeline = ml_resources["model_pipeline"]
    feature_names = ml_resources["feature_names"]
    
    if not explainer or not pipeline:
        raise HTTPException(status_code=503, detail="XAI not ready")
        
    try:
        df = pd.DataFrame([transaction.dict(exclude={'transaction_id'})])
        scaled_data = pipeline.named_steps['scaler'].transform(df)
        
        shap_results = explainer(scaled_data)
        vals = shap_results.values[0, :, 1] if len(shap_results.values.shape) == 3 else shap_results.values[0]
        
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
    try:
        return run_investigation(transaction_id)
    except Exception as e:
        logger.error(f"Agent Investigation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))