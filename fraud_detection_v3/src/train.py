import os
import pandas as pd
import numpy as np
import mlflow
import mlflow.xgboost
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, f1_score, average_precision_score
import shap

def load_data():
    """
    Loads the Kaggle Credit Card Fraud dataset.
    Note: In a real environment, you would use 'kaggle datasets download' 
    or pull from an S3 bucket. Here we assume creditcard.csv is in data/
    """
    data_path = "/home/tejaswee/Projects/Fraud_Detection/Data/creditcard.csv"
    if not os.path.exists(data_path):
        print(f"Dataset not found at {data_path}. Generating synthetic SOTA-structured data for demonstration...")
        # Create a mock Kaggle structure: Time, V1-V28, Amount, Class
        samples = 20000
        data = np.random.randn(samples, 30)
        # 0.17% fraud rate like real Kaggle data
        is_fraud = (np.random.rand(samples) < 0.0017).astype(int)
        data[is_fraud == 1, :5] += 5 # Make fraud distinguishable for the SOTA model
        cols = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
        df = pd.DataFrame(data, columns=cols)
        df['Class'] = is_fraud
        return df
    
    return pd.read_csv(data_path)

def train_fraud_model():
# We point to localhost:5000 where the docker container is exposed
    uri = "http://localhost:5000"
    mlflow.set_tracking_uri(uri)
    
    print(f"Connecting to MLflow Tracking Server at {uri}...")
    
    # Simple check to ensure server is up before wasting compute
    try:
        mlflow.search_experiments()
        print("Connection successful!")
    except Exception as e:
        print(f"❌ Could not connect to MLflow server. Is Docker running? Error: {e}")
        return

    # --- CRITICAL FIX 2: ENSURE EXPERIMENT EXISTS ---
    experiment_name = "Fraud_Detection_V3_SOTA"
    try:
        mlflow.set_experiment(experiment_name)
    except:
        mlflow.create_experiment(experiment_name)
        mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name="XGBoost_SOTA_Tuning"):
        # 2. Data Preparation
        df = load_data()
        X = df.drop('Class', axis=1)
        y = df['Class']
        
        imbalance_ratio = (len(y) - y.sum()) / y.sum()
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # 3. Define Pipeline
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', XGBClassifier(
                n_estimators=500,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=imbalance_ratio,
                use_label_encoder=False,
                eval_metric='aucpr',
                random_state=42
            ))
        ])

        # 4. Train
        print("Training SOTA XGBoost model...")
        pipeline.fit(X_train, y_train)

        # 5. Evaluate
        probs = pipeline.predict_proba(X_test)[:, 1]
        predictions = pipeline.predict(X_test)
        
        aucs_pr = average_precision_score(y_test, probs)
        f1 = f1_score(y_test, predictions)
        
        # Log params and metrics
        mlflow.log_params(pipeline.named_steps['classifier'].get_params())
        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("auc_pr", aucs_pr)
        
        # 6. SHAP Explainability
        print("Calculating SHAP values...")
        # Note: We must unwrap the pipeline to get the model for SHAP
        model = pipeline.named_steps['classifier']
        explainer = shap.TreeExplainer(model)
        
        # Log explainer metadata
        mlflow.log_dict({
            "explainer_type": "TreeExplainer", 
            "feature_names": X.columns.tolist()
        }, "explainer_info.json")

        # 7. Log Model
        print("Logging model artifact to MLflow...")
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="fraud_model_pipeline",
            registered_model_name="FraudDetectionSOTA"
        )
        
        print(f"Success! F1: {f1:.4f}, AUC-PR: {aucs_pr:.4f}")
        print("Model has been registered in the MLflow Model Registry.")

if __name__ == "__main__":
    train_fraud_model()