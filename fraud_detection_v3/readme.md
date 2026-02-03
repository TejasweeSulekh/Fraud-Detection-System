# Real-Time Fraud Detection System (v3)
This repository contains the source code for a next-generation, real-time, and explainable fraud detection pipeline built for scalability, low-latency, and production-readiness.

## 1. Problem Statement
Traditional fraud detection systems often run in batch, identifying fraud after it has occurred. This is insufficient for modern financial systems. A robust solution must:

1. **Detect fraud in real-time** (sub-second) to prevent malicious transactions from ever completing

2. **Scale to millions** of transactions per second during peak loads without performance degradation

3. **Being explainable** this should provide clear explaination for the customers and auditors for declined transactions

This project builds an end-to-end system the solves these challenges, Evloving from a professional pipeline (v3.0) to a full-scale distributed streaming application (v3.1) with production grade MLOps (v3.2).

## 2. Tech Stack Overview

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Core ML** | Python 3.10 | Base language for all services and modeling. |
| | XGBoost | High-performance gradient-boosted model for superior accuracy. |
| | scikit-learn | Data preprocessing, pipelines, and model evaluation. |
| | SHAP | Model explainability (XAI) to understand predictions. |
| **MLOps & Serving** | MLflow | Experiment tracking, model registry, and artifact management. |
| | FastAPI | High-performance, asynchronous API for serving the ML model. |
| **Streaming (v3.1)** | Apache Kafka | Real-time, distributed event streaming bus. |
| | Apache Flink | Stateful stream processing for real-time feature engineering. |
| | Redis | In-memory online feature store for millisecond-latency lookups. |
| **Dependency Mgmt** | Poetry | Deterministic dependency management and virtual environment handling |
| **DevOps (v3.1/3.2)** | Docker | Containerization of all microservices for portability. |
| | Docker Compose | Local orchestration of the entire multi-service stack. |
| | GitHub Actions | CI/CD automation for testing and code quality checks. |
| **Monitoring (v3.2)** | PostgreSQL | Database for logging all transaction predictions. |
| | Streamlit | Interactive dashboard for monitoring model drift. |

## 3. Project Roadmap & Detailed Tasks

**v3.0 The Advanced, Explainable ML Pipeline (Current Focus)**

Goal: Create the intelligent core of our system. Success means having a high-performing model that is not a "black box," but is trackable, servable, and explainable.

-   **Phase 1: Project Foundation & Setup**
    - [✔️] **Initialize Git repository**: Run `git init` and create a `.gitignore` file 
    - [✔️] **Initialize Poetry**: Run `poetry init` to create `pyproject.toml` for deterministic dependency management
    - [] **Install and Lock Dependency**: Use `poetry add xgboost mlflow fastapi uvicorn shap scikit-learn pandas` to manage versions correctly via `poetry.lock`
    - [✔️] **Establish core project structure**: Create `src/`, `data/`, `notebooks/` directories

- **Phase 2: Advanced Modeling & Experiment Tracking**
    - [✔️] **Develop a reproducible training script**: Create `src/train.py` for data loading and XGBoost training
    - [✔️] **Integrate MLflow**: Use `mlflow.start_run()` to log params, metrics (Precision/Recall), and artifacts
    - [✔️] **Validate experiment tracking**: Confirm runs are viewable via `mlflow ui` (run via `poetry run mlflow ui`)
- **Phase 3: Model Serving via API**
    - [✔️] **Build a FastAPI service**: Create `src/inference_service/main.py`
    - [] **Load production model**: Implement logic to pull the latest model from the MLflow Model Registry
    - [✔️] **Create /predict endpoint**: Accept transaction JSON and return a fraud score
- **Phase 4: Model Explainability (XAI)**
    - [✔️] **Log SHAP explainer**: In `train.py`, log a `shap.TreeExplainer` as an MLflow artifact
    - [✔️] **Create `/explain` endpoint**: Provide feature contribution analysis for any given transaction

**v3.1: The Real-Time Streaming Architecture**

**Goal**: Re-architect for a live data system capable of handling massive scale.

- **Phase 1: Containerization & Orchestration**
    - [] Write a `Dockerfile` for the FastAPI service using Poetry for multi-stage builds
    - [] Create `docker-compose.yml` with `Kafka`, `Zookeeper`, and `Redis`
- **Phase 2: Real-Time Data Ingestion**
    - [] Build a `Transaction Ingestor` service to publish data to a Kafka topic
    - [] Dockerize the ingestor service
- **Phase 3: Stateful Stream Processing**
    - [] Build a `Feature Engine` using Apache Flink to consume from Kafka
    - [] Implement real-time feature logic using Redis for state storage
    - [] Publish "enriched" transactions to an `enriched_transactions` Kafka topic
- **Phase 4: Final Inferencing Pipeline**
    - [] Create an `Inference Consumer` to subscribe to enriched data
    - [] Trigger model scoring via the FastAPI `/predict` endpoint

---
Phase 5: Observability & Interaction.

Here is the roadmap for this phase. We will add three distinct layers to your current setup:

1. The "Routine" (Automated Health/Smoke Test)
You asked: "Where this check can happen when the server goes online?"

This is best implemented as a "Smoke Test Script".

What it is: A Python script (check_system.py) that runs outside the containers (or in a temporary container).

When it runs: Immediately after you run docker-compose up.

What it checks:

MLflow: Is the server responding on port 5000?

Inference: Is the API responding on port 8000?

Model Availability: Can the API actually load the model?

End-to-End: If we send a dummy transaction, do we get a prediction (0 or 1) back?

2. The User Interface (Streamlit)
We will add a simple, friendly website where you (or a fraud analyst) can:

Manually enter transaction details (using sliders/inputs).

Click "Detect Fraud."

See the probability score visually.

Bonus: See a "System Status" light (Green/Red) powered by your health check.

3. Monitoring (Prometheus & Grafana)
This is for the "heartbeat" of the system over time.

Prometheus: Silently records metrics (e.g., "Inference API took 0.1s", "50 requests per minute").

Grafana: A dashboard with graphs showing traffic spikes or errors.
---

**v3.2: The MLOps & Production Polish**

**Goal**: Implement professional monitoring and automation

- **Phase 1: CI/CD Automation**
    - [] Set up GitHub Actions for automated linting (`black`/`flake8`) using `poetry run`
    - [] Integrate `pytest` into the CI pipeline via `poetry run pytest`
- **Phase 2: Model Monitoring & Observability**
    - [] Deploy `PostgreSQL` to log all production predictions
    - [] Build a `Streamlit` dashboard to visualize Data Drift and Concept Drift
- **Phase 3: Final Documentation**
    - [] Create a comprehensive architecture diagram
    - [] Write detailed API documentation and ensure professional docstrings throughout

TODO: Right now have to implement redis and kafka and then check what extra things can be implemented.