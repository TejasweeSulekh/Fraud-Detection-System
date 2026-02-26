# 🧠 Source Code Documentation

This directory contains the Python source code for the microservices. Below is a technical breakdown of each script.

## 📦 Module Overview

### 1. app.py (Inference Service)
The entry point for the FastAPI application.

* **Startup Logic (`load_artifacts`):**
    * Initiates the database connection via `init_db()`.
    * Connects to Redis.
    * **Retry Loop:** Attempts to load the model from MLflow (`models:/FraudDetectionSOTA/latest`) up to 7 times. This is crucial for handling container startup race conditions.
* **`/predict` Endpoint:**
    * **Caching Strategy:** Checks Redis using key pattern `pred:{transaction_id}`.
    * **Batch Processing:** Only runs inference on transactions not found in the cache.
    * **Write-Back:** Saves results to Redis (TTL 1 hour) and PostgreSQL asynchronously.
* **`/explain` Endpoint:**
    * Loads the `shap.TreeExplainer` from global state.
    * Returns the top 5 features contributing to the fraud score.

### 2. consumer.py (Kafka Worker)
Runs as a standalone process to bridge Kafka and the API.

* **Configuration:** Connects to `transaction_stream` with Group ID `fraud-detector-group-1`.
* **Message Loop:**
    * Polls Kafka (1.0s timeout).
    * Deserializes JSON.
    * POSTs data to `http://inference-service:8000/predict`.
* **Logging:** Uses `logger.warning` for fraud alerts (which appear in red in many log viewers) and `logger.debug` for legit transactions.

### 3. producer.py (Traffic Simulator)
Generates synthetic data to mimic user activity.

* **Data Generation:** Creates a dictionary with Time, Amount, and anonymous features V1-V28.
* **UUIDs:** Assigns a unique `uuid4` to every transaction to test the caching logic downstream.
* **Throttling:** Sleeps for 0.5s between messages to simulate a steady throughput of ~2 TPS.

### 4. train_in_docker.py (MLOps Pipeline)
Executed by the `init-model` container.

* **`wait_for_mlflow(uri)`:** A custom robust check that pings the MLflow server every 2 seconds until it returns HTTP 200. This prevents the training job from crashing before the server is ready.
* **Pipeline:**
    * **StandardScaler:** Normalizes the input features.
    * **RandomForestClassifier:** The core classification model.
* **Artifacts:** Saves the model to MLflow with the "Production" tag.

### 5. dashboard.py (Streamlit UI)
Visualizes data from the PostgreSQL database.

* **Refresh Logic:** Uses `st.rerun()` with a 2-second sleep timer to simulate a live feed.
* **Investigator Mode:**
    * Includes a "Pause Live Updates" checkbox.
    * When paused, users can select a `transaction_id`.
    * Triggers a request to the API's `/explain` endpoint and renders the response using `plotly.express`.

### 6. database.py (ORM Layer)
* **Engine:** SQLAlchemy engine connecting to `postgresql://fraud_user...`.
* **Schema:** `PredictionLog` table stores inputs (JSON), outputs (Probabilities), and latency metrics.

### 7. utils.py (Helpers)
* **`download_and_extract_data`:** Handles the specific "confirm token" logic required to download large files (like the credit card dataset) programmatically from Google Drive.

## 🔄 Environment Variables

Ensure these are set in `docker-compose.yml` for the scripts to function:

| Variable | Used By | Purpose |
| :--- | :--- | :--- |
| `MLFLOW_TRACKING_URI` | `app.py`, `train_in_docker.py` | Location of the MLflow server |
| `REDIS_HOST` | `app.py` | Redis connection string |
| `DATABASE_URL` | `app.py`, `dashboard.py` | PostgreSQL connection string |
| `KAFKA_BOOTSTRAP_SERVERS` | `consumer.py`, `producer.py` | Kafka broker address |