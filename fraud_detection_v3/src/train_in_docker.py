# src/train_in_docker.py
import mlflow
import mlflow.sklearn
import pandas as pd
import os
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from src.utils import download_and_extract_data

# --- CONFIGURATION ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
# REPLACE THIS with your actual Google Drive File ID
FILE_ID = "1q946EqSrkl1_BnbycMoSJe5As3VmuJQn" 
DATA_DIR = "data"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Trainer")

mlflow.set_tracking_uri(MLFLOW_URI)
mlflow.set_experiment("FraudDetection_Docker_Build")

def train():
    logger.info("Starting Training Pipeline...")
    
    # 1. Data Ingestion
    csv_path = download_and_extract_data(FILE_ID, DATA_DIR)
    
    if csv_path and os.path.exists(csv_path):
        logger.info(f"Loading real data from {csv_path}...")
        df = pd.read_csv(csv_path)
        
        # Depending on dataset size, you might want to sample for speed during dev
        # df = df.sample(frac=0.1, random_state=42) 
        
        X = df.drop(['Class'], axis=1) # Assuming 'Class' is target
        y = df['Class']
    else:
        logger.warning("Real data not found. Falling back to SYNTHETIC data.")
        X, y = make_classification(n_samples=1000, n_features=30, n_informative=20, random_state=42)
        # Fix column names to match schema (Time, V1...V28, Amount)
        cols = ['Time'] + [f"V{i}" for i in range(1, 29)] + ['Amount']
        X = pd.DataFrame(X, columns=cols)

    # 2. Split Data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 3. Define Pipeline
    # Using Random Forest for stability. XGBoost is preferred for production performance.
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(n_estimators=50, n_jobs=-1))
    ])

    # 4. Train & Register
    with mlflow.start_run():
        logger.info("Training Model...")
        pipeline.fit(X_train, y_train)
        
        logger.info("Registering Model to MLflow...")
        mlflow.sklearn.log_model(
            pipeline, 
            "model", 
            registered_model_name="FraudDetectionSOTA"
        )
        
        # Log metrics
        accuracy = pipeline.score(X_test, y_test)
        mlflow.log_metric("accuracy", accuracy)
        logger.info(f"Model Registered! Accuracy: {accuracy:.4f}")

if __name__ == "__main__":
    train()