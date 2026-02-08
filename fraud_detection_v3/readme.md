# 🛡️ Real-Time Fraud Detection System (v3.1)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-orange)
![MLflow](https://img.shields.io/badge/MLOps-MLflow-blueviolet)
![Kafka](https://img.shields.io/badge/Streaming-Kafka-black)

A complete, containerized MLOps pipeline for detecting fraudulent credit card transactions in real-time. This system simulates a production environment with event streaming, distributed caching, model versioning, and an explainable AI (XAI) dashboard.

## 🚀 Key Features

* **Real-Time Inference:** sub-50ms latency using **FastAPI** and **Redis** caching.
* **Event Streaming:** Decoupled architecture using **Apache Kafka** for high-throughput transaction processing.
* **Automated MLOps:** Self-healing training pipeline that automatically retrains and versions models using **MLflow**.
* **Explainable AI (XAI):** Integrated **SHAP** (SHapley Additive exPlanations) to provide "Why" behind every fraud alert.
* **Live Monitoring:** Interactive **Streamlit** dashboard for visualizing fraud trends and investigating alerts.

## 🏗️ Architecture

The system is composed of 6 microservices orchestrated via Docker Compose:

1.  **Producer:** Simulates a stream of credit card transactions (Legit & Fraud).
2.  **Kafka:** Buffers transactions for asynchronous processing.
3.  **Consumer:** Reads from Kafka, sends data to the Inference API.
4.  **Inference API:** The brain. Loads the model from MLflow, checks Redis cache, predicts fraud, and logs to Postgres.
5.  **Dashboard:** A UI for analysts to monitor traffic and audit suspicious transactions.
6.  **MLflow & Postgres:** Backend for model registry and persistent data storage.

## 🛠️ Tech Stack

* **Language:** Python 3.12
* **ML Frameworks:** Scikit-Learn, SHAP, MLflow
* **Streaming:** Confluent Kafka, Zookeeper
* **Web/API:** FastAPI, Streamlit
* **Database/Cache:** PostgreSQL, Redis
* **Infrastructure:** Docker, Docker Compose

## ⚡ Quick Start

You can spin up the entire system with a single command. No local Python environment is required.

### Prerequisites
* Docker Desktop installed and running.

### Installation

1.  **Clone the repository**
    ```bash
    git clone Fraud-Detection-System
    cd ./Fraud-Detection-System/fraud_detection_v3
    ```

2.  **Launch the System**
    ```bash
    docker-compose up --build
    ```
    *Note: The first run may take a few minutes as it downloads the dataset and trains the initial model.*

3. **What Happens**

    * **mlflow-server** starts.

    * **init-model** will stay in "Created" state and wait until mlflow-server is healthy (responding to curl).

    * Once MLflow is green, init-model runs train_in_docker.py.

    * **train_in_docker.py** will now successfully download the data (using the fixed utils.py) and log the model.

    * Once init-model finishes (exits with code 0), inference-service will start.

    * The rest of the system spins up.

4.  **Access the Services**
    * **Dashboard:** [http://localhost:8501](http://localhost:8501) 
    * **MLflow UI:** [http://localhost:5000](http://localhost:5000)
    * **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

## 📂 Project Structure

```text
├── data/               # Local data storage (mounted volume)
├── mlruns/             # MLflow artifact storage
├── src/                # Source code for all microservices
│   ├── app.py          # FastAPI Inference Service
│   ├── consumer.py     # Kafka Consumer logic
│   ├── dashboard.py    # Streamlit Dashboard
│   ├── train_in_docker.py # Automated Training Script
│   └── ...
├── docker-compose.yml  # Orchestration config
└── Dockerfile          # Unified container definition

