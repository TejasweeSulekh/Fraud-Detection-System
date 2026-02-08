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
    data_path = "data/creditcard.csv"
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
    # 1. Setup MLflow
    mlflow.set_experiment("Fraud_Detection_V3_SOTA")

    with mlflow.start_run(run_name="XGBoost_SOTA_Tuning"):
        # 2. Data Preparation
        df = load_data()
        X = df.drop('Class', axis=1)
        y = df['Class']
        
        # Calculate scale_pos_weight for imbalance: (count of negative / count of positive)
        # This is a SOTA technique for fraud detection
        imbalance_ratio = (len(y) - y.sum()) / y.sum()
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # 3. Define Pipeline (Scaling + XGBoost)
        # SOTA parameters for XGBoost on imbalanced data
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', XGBClassifier(
                n_estimators=500,        # More trees for complexity
                max_depth=4,             # Shallower trees prevent overfitting on noise
                learning_rate=0.05,      # Slower learning is more robust
                subsample=0.8,           # Use 80% of data per tree to prevent overfitting
                colsample_bytree=0.8,    # Use 80% of features per tree
                scale_pos_weight=imbalance_ratio, # CRITICAL: Handle the 0.17% imbalance
                use_label_encoder=False,
                eval_metric='aucpr',      # Optimize for Area Under Precision-Recall Curve (SOTA for fraud)
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
        # Industry Standard: Explaining why a high-risk score was generated
        print("Calculating SHAP values...")
        explainer = shap.TreeExplainer(pipeline.named_steps['classifier'])
        # We store the explainer metadata to be used by the API in Phase 4
        mlflow.log_dict({"explainer_type": "TreeExplainer", "feature_names": X.columns.tolist()}, "explainer_info.json")

        # 7. Log Model & Pipeline
        # We log using the sklearn flavor because our model is inside a Pipeline
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="fraud_model_pipeline",
            registered_model_name="FraudDetectionSOTA"
        )
        
        print(f"Success! F1: {f1:.4f}, AUC-PR: {aucs_pr:.4f}")
        print("Model has been registered in the MLflow Model Registry.")

if __name__ == "__main__":
    train_fraud_model()