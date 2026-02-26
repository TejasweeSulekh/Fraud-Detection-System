import mlflow
import mlflow.sklearn
import pandas as pd
import os
import logging
import time
import requests
from sklearn.ensemble import RandomForestClassifier
# from xgboost import XGBClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from src.utils import download_and_extract_data

# --- CONFIGURATION ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
FILE_ID = "1q946EqSrkl1_BnbycMoSJe5As3VmuJQn" 
DATA_DIR = "data"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Trainer")

def wait_for_mlflow(uri, max_retries=600, delay=1):
    """Waits for MLflow server to be ready before proceeding."""
    logger.info(f"Waiting for MLflow at {uri}...")
    for i in range(max_retries):
        try:
            response = requests.get(uri)
            if response.status_code < 500:
                logger.info("MLflow is up and running.")
                return True
        except requests.exceptions.ConnectionError:
            pass
        
        logger.info(f"MLflow not ready yet. Retrying in {delay}s ({i+1}/{max_retries})...")
        time.sleep(delay)
    
    logger.error("MLflow failed to respond. Exiting.")
    return False

def train():
    # 1. Wait for Infrastructure
    if not wait_for_mlflow(MLFLOW_URI):
        raise Exception("MLflow unavailable")

    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("FraudDetection_Docker_Build")
    
    logger.info("Starting Training Pipeline...")
    
    # 2. Data Ingestion
    csv_path = download_and_extract_data(FILE_ID, DATA_DIR)
    
    if csv_path and os.path.exists(csv_path):
        logger.info(f"Loading real data from {csv_path}...")
        df = pd.read_csv(csv_path)
        
        # Sampling for speed during dev
        # df = df.sample(frac=0.1, random_state=42) 
        
        X = df.drop(['Class'], axis=1)
        y = df['Class']
    else:
        logger.warning("Real data not found. Falling back to SYNTHETIC data.")
        X, y = make_classification(n_samples=1000, n_features=30, n_informative=20, random_state=42)
        cols = ['Time'] + [f"V{i}" for i in range(1, 29)] + ['Amount']
        X = pd.DataFrame(X, columns=cols)

    # 3. Split Data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 4. Define Pipeline
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        # CHANGE THIS LINE:
        # ('classifier', XGBClassifier(
        #     n_estimators=100,
        #     learning_rate=0.1,
        #     max_depth=5,
        #     use_label_encoder=False,
        #     eval_metric='logloss',
        #     n_jobs=-1
        # ))
        ('classifier', RandomForestClassifier(n_estimators=50, n_jobs=-1))
    ])

    # 5. Train & Register
    with mlflow.start_run():
        logger.info("Training Model...")
        pipeline.fit(X_train, y_train)
        
        logger.info("Registering Model to MLflow...")
        mlflow.sklearn.log_model(
            pipeline, 
            "model", 
            registered_model_name="FraudDetectionSOTA"
        )
        
        accuracy = pipeline.score(X_test, y_test)
        mlflow.log_metric("accuracy", accuracy)
        logger.info(f"Model Registered! Accuracy: {accuracy:.4f}")

if __name__ == "__main__":
    train()