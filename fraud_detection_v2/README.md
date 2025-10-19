# Real-Time Fraud Detection System (V2.0)

This project (V2.0) refactors the fraud detection system into a scalable, real-time, event-driven architecture. It replaces the V1 monolithic backend and PostgreSQL database with a set of decoupled microservices that communicate using a Kafka message broker.

This new architecture is designed for high throughput and scalability. The `transaction-api` (the web server) is no longer responsible for fraud logic; it simply ingests transactions and serves the frontend. The `fraud-detector` service runs independently, allowing its logic to be updated or scaled without any downtime for the main API.

---

## V2.0 Architecture

The system is now composed of two main services and a Kafka message bus:

1.  **`transaction-api` (FastAPI):**
    * Serves the static frontend (HTML/JS) at the `/frontend` endpoint
    * Receives new transactions via an `HTTP POST` at `/transaction`
    * Produces these new transactions as messages to the `transactions` Kafka topic
    * Hosts a `/ws` WebSocket endpoint to broadcast results to the frontend
    * Consumes from the `transaction-results` Kafka topic in a background thread to get results

2.  **`fraud-detector` (Python):**
    * A "headless" worker that subscribes to the `transactions` Kafka topic
    * Applies the rule-based fraud logic to each message it receives
    * Produces its findings (the original transaction + fraud score) as messages to the `transaction-results` topic

This decoupled flow ensures that even if the `fraud-detector` is slow or crashes, the `transaction-api` can continue to accept new transactions without interruption.

### Data Flow
`[Frontend]` -> (`HTTP POST`) -> `[API]` -> (`'transactions' Topic`) -> `[Fraud Detector]` -> (`'transaction-results' Topic`) -> `[API]` -> (`WebSocket Push`) -> `[Frontend]`

---

## Features (V2.0)

* **Event-Driven:** The system is built around asynchronous message passing, not direct API calls
* **Decoupled Microservices:** The API (`transaction-api`) and the fraud logic (`fraud-detector`) are separate services that can be scaled independently
* **Real-Time WebSocket Feed:** The frontend receives fraud analysis results in real-time without needing to poll the server
* **Scalable Workers:** You can run multiple instances of the `fraud-detector` service to process transactions in parallel
* **Message Persistence:** Kafka acts as a durable, persistent log of all transactions and results
* **Containerized:** All services (Zookeeper, Kafka, API, Detector) are fully managed by Docker Compose

---

## Tech Stack
| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Web API / Gateway** | Python, FastAPI, Uvicorn | Serves frontend, receives transactions, broadcasts WebSocket results |
| **Detection Service** | Python, kafka-python | `fraud-detector` worker. Consumes, processes, and produces messages |
| **Message Broker** | Kafka | Decouples services, persists transaction and result streams |
| **Orchestration** | Zookeeper | Manages the Kafka cluster |
| **Frontend** | Vanilla JavaScript, HTML, TailwindCSS | User interface and real-time WebSocket client |
| **DevOps** | Docker, Docker Compose | Containerization and service orchestration |

---

## Getting Started
### Prerequisites
* [Docker](https://www.docker.com/products/docker-desktop/) and **Docker Compose** must be installed on your system.

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone <your-repository-url>
    cd fraud_detection_v2
    ```
2.  **No `.env` file needed!** Configuration (like the Kafka server address) is handled directly in the `docker-compose.yml` file for simple setup.

---

## How to Run the Application

1.  **Build and Run the Containers:**
    From the project's root directory (`fraud_detection_v2/`), run:
    ```sh
    docker-compose up --build
    ```
    This command will build the images, start all four containers (Zookeeper, Kafka, API, Detector), and show you the live, combined logs.

2.  **Wait for the services to boot:**
    It may take **30-60 seconds** for Kafka to become fully operational and for the Python services to connect. You will see retry messages in the logs, which is normal. Wait until you see "Successfully connected..." messages from `transaction-api` and `fraud-detector`.

3.  **Access the Services:**
    * **Frontend Application**: Open your browser and go to [http://localhost:8000/frontend/index.html](http://localhost:8000/frontend/index.html)
    * **Backend API Docs**: You can still view the API docs at [http://localhost:8000/docs](http://localhost:8000/docs)