import os
import pandas as pd
import numpy as np
import mlflow
import mlflow.xgboost
import mlflow.sklearn
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score, average_precision_score
import shap

# --- CONFIGURATION ---
# Use environment variable for the tracking URI, default to localhost if not set
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
EXPERIMENT_NAME = "Fraud_Detection_V3_SOTA"
MODEL_NAME = "FraudDetectionSOTA"

def load_data():
    """
    Loads creditcard.csv from a 'data' folder in the project root.
    Falls back to synthetic data if the file is missing.
    """
    # Look for data relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to root, then into data/
    project_root = os.path.dirname(current_dir)
    data_path = os.path.join(project_root, "data", "creditcard.csv")

    if os.path.exists(data_path):
        print(f"📂 Loading real dataset from {data_path}...")
        return pd.read_csv(data_path)
    
    print(f"⚠️ Dataset not found at {data_path}. Generating SYNTHETIC data...")
    # Generate mock data (same logic as before)
    samples = 10000 # Reduced slightly for faster local testing
    data = np.random.randn(samples, 30)
    # Simulate 0.2% fraud
    is_fraud = (np.random.rand(samples) < 0.002).astype(int)
    # Make fraud features distinct so the model actually learns something
    data[is_fraud == 1, :5] += 5 
    
    cols = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
    df = pd.DataFrame(data, columns=cols)
    df['Class'] = is_fraud
    return df

def train_fraud_model():
    # 1. Setup MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    print(f"🔌 Connecting to MLflow at {MLFLOW_TRACKING_URI}...")
    
    # Ensure experiment exists
    try:
        mlflow.set_experiment(EXPERIMENT_NAME)
    except:
        print(f"Creating new experiment: {EXPERIMENT_NAME}")
        mlflow.create_experiment(EXPERIMENT_NAME)
        mlflow.set_experiment(EXPERIMENT_NAME)

    # 2. Start Run
    with mlflow.start_run(run_name="XGBoost_Pipeline_Train"):
        print("🚀 Starting training run...")
        
        # Load & Split Data
        df = load_data()
        X = df.drop('Class', axis=1)
        y = df['Class']
        
        # Calculate scale_pos_weight for imbalance
        # (count(negative) / count(positive))
        imbalance_ratio = (y == 0).sum() / (y == 1).sum()
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # 3. Define Pipeline
        # We wrap Scaler + XGBoost together. 
        # This is critical so the API doesn't need to manually scale inputs.
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', XGBClassifier(
                n_estimators=100,      # Kept low for demo speed; increase for prod
                max_depth=4,
                learning_rate=0.1,
                scale_pos_weight=imbalance_ratio,
                eval_metric='aucpr',
                random_state=42
            ))
        ])

        # 4. Train
        print("🧠 Training model...")
        pipeline.fit(X_train, y_train)

        # 5. Evaluate
        preds = pipeline.predict(X_test)
        probs = pipeline.predict_proba(X_test)[:, 1]
        
        f1 = f1_score(y_test, preds)
        auc_pr = average_precision_score(y_test, probs)
        
        print(f"📊 Metrics: F1={f1:.4f}, AUC-PR={auc_pr:.4f}")
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("auc_pr", auc_pr)
        
        # Log parameters
        clf_params = pipeline.named_steps['classifier'].get_params()
        mlflow.log_params(clf_params)

        # 6. SHAP Signature & Artifacts
        # We log a small example of input data so MLflow knows the schema
        signature = mlflow.models.infer_signature(X_train.head(), pipeline.predict(X_train.head()))

        # 7. Log Model
        print("💾 Logging model to MLflow...")
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="fraud_model_pipeline",
            registered_model_name=MODEL_NAME, # Registers it directly to Model Registry
            signature=signature
        )
        print(f"✅ Model registered as '{MODEL_NAME}'")

if __name__ == "__main__":
    train_fraud_model()