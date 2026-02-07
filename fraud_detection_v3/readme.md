# 🛡️ Real-Time Fraud Detection System (End-to-End MLOps)

A scalable, event-driven machine learning pipeline that detects fraudulent credit card transactions in real-time.

Built with **Kafka** for streaming, **FastAPI** for inference, **Redis** for caching, **PostgreSQL** for persistence, and **Docker** for containerization.

---

## 🚀 Quick Start

### Prerequisites
* **Docker Desktop** (Running)
* **Python 3.9+** (For running client scripts locally)
* **Make** (Optional, for shortcut commands)

### 1. Start the Infrastructure
This command spins up Zookeeper, Kafka, Redis, Postgres, MLflow, and the Inference API.
```bash
make up
# OR: docker-compose up -d --build
```
Wait ~30 seconds for all services to initialize.

2. Install Local Dependencies
To run the data generator (producer) and processor (consumer) locally:

```Bash
pip install confluent-kafka requests
```

3. Run the Pipeline
Open two separate terminal windows:

Terminal A: The Consumer (The Processor) Listens for transactions and detects fraud.

```bash
make consumer
# OR: python src/consumer.py
```

4. Verify Results
Check the PostgreSQL database to confirm transactions are being saved:

```bash
make check-db
```

🏗️ Architecture
The system follows a Producer-Consumer microservices pattern:

1. Ingestion: The producer.py script mimics a POS terminal, pushing transactions to a Kafka Topic (transaction_stream).

2. Processing: The consumer.py service subscribes to the topic. It acts as a bridge, forwarding data to the Inference API.

3. Inference: The FastAPI service (inference-service):

-  Checks Redis to see if this transaction was already processed (Deduplication/Caching).

-  If new, it loads the model (from MLflow) and predicts fraud probability.

-  Saves the result to PostgreSQL for audit/analytics.

4. Storage:

- Redis: TTL-based cache for low-latency lookups.

- PostgreSQL: Permanent storage for all prediction logs.


🛠️ Tech Stack

Component,Technology,Purpose
Streaming,Apache Kafka,High-throughput event buffering & decoupling.
API,FastAPI,High-performance async REST API for model inference.
Model Serving,MLflow,Model versioning and artifact management.
Caching,Redis,Low-latency deduplication (prevents re-computing known transactions).
Database,PostgreSQL,Persistent storage for fraud logs and analytics.
Containerization,Docker & Compose,Reproducible environment management.

📂 Project Structure

Plaintext
├── src/
│   ├── app.py             # FastAPI Application (The Brain)
│   ├── producer.py        # Fake Transaction Generator
│   ├── consumer.py        # Kafka Listener
│   ├── database.py        # Postgres Connection Logic
│   ├── train_in_docker.py # Script to retrain model inside container
│   └── ...
├── models/                # Local model storage
├── docker-compose.yml     # Infrastructure orchestration
├── Dockerfile             # API Container definition
├── Makefile               # Shortcut commands
└── README.md              # Documentation


🧠 Key Design Decisions
Why Kafka?
Instead of a direct HTTP call from the credit card terminal to the API, we use Kafka to decouple the systems. This ensures that if the API goes down, transactions aren't lost—they are buffered in the queue until the system recovers.

Why Redis?
Fraud detection requires speed. We use Redis as a "Look-aside Cache." If a transaction ID is seen twice (e.g., a retry), we return the cached result in <1ms instead of running the heavy ML model again.

Why Train in Docker?
To avoid "it works on my machine" errors. The training script runs inside the same Linux environment as the API, ensuring joblib and pickle binary compatibility for libraries like XGBoost/Scikit-Learn.