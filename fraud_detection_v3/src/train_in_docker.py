import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import RandomForestClassifier # Using RF for stability, or swap to XGBoost
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.datasets import make_classification

# MLflow Config
mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("FraudDetection_Docker_Build")

def train():
    print("🚀 Starting Training inside Docker...")
    
    # 1. Generate Dummy Data (matching your schema)
    # We use dummy data just to fix the "Architecture Mismatch" crash quickly.
    # In real life, you'd mount your CSV to /app/data/
    X, y = make_classification(n_samples=1000, n_features=29, n_informative=20, random_state=42)
    
    # Feature names V1..V28 + Time (29 columns) - we simulate the structure
    cols = ['Time'] + [f"V{i}" for i in range(1, 29)]
    X_df = pd.DataFrame(X, columns=cols)
    # Just setting 'Amount' as V28 for simplicity or adding it
    X_df['Amount'] = 100.0 
    
    # 2. Define Pipeline
    # Using RandomForest momentarily to ensure stability, change back to XGBoost if you have it installed
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(n_estimators=10))
    ])

    # 3. Train & Register
    with mlflow.start_run():
        print("🧠 Training Model...")
        pipeline.fit(X_df, y)
        
        print("💾 Registering Model to MLflow...")
        mlflow.sklearn.log_model(
            pipeline, 
            "model", 
            registered_model_name="FraudDetectionSOTA"
        )
        print("✅ Model Registered! Version updated.")

if __name__ == "__main__":
    train()