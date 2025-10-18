# Real-Time Fraud Detection System (V1.0)

This project is a full-stack web application that provides a real-time fraud detection service. It features a Python (FastAPI) backend, a PostgreSQL database, and a vanilla JavaScript frontend. The entire application is containerized with Docker for easy setup and deployment.

The first version (V1.0) implements a simple rule-based engine for detecting fraudulent transaction.

---

## Features (V1.0)

* **Restful API**: A backend API to submit and retrieve transaction
* **Rule-Based Engine**: A simple set of rules to flag a transaction as fraudulent (e.g. based on amount, merchant name...)
* **Database Persistence**: All transactions and their datatypes are saved in a PostgreSQL database.
* **Web Interface**: A simple frontend to submit the transaction and view a live-updating history of all the transactions
* **Containerized**: The full application (backend, database) is managed in Docker compose

---

## Tech Stack
| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python, FastAPI | Core API framework, data validation |
| **Database** | PostgreSQL | Data storage for transactions |
| **ORM** | SQLAlchemy | Python-to-SQL database communication |
| **Frontend** | Vanilla JavaScript, HTML, CSS | User interface |
| **DevOps** | Docker, Docker Compose | Containerization and service orchestration |
| **Testing** | Pytest, Requests | Unit and integration testing |

---

## Getting Started 
### Prerequisites
* [Docker](https://www.docker.com/products/docker-desktop/) and **Docker Compose** must be installed on your system.

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone <your-repository-url>
    cd fraud_detection_v1
    ```

2.  **Create an environment file:**
    Create a file named `.env` in the project root. This file stores your database credentials.

    ```
    # .env
    POSTGRES_USER=user
    POSTGRES_PASSWORD=password
    POSTGRES_DB=fraud_db
    DATABASE_URL=postgresql://user:password@db:5432/fraud_db
    ```

---

## How to Run the Application

1.  **Build and Run the Containers:**
    From the project's root directory, run:
    ```sh
    docker-compose up --build
    ```
    This command will build the Docker images, start the backend and database containers, and show you the live logs.

2.  **Access the Services:**
    * **Backend API Docs**: Open your browser and go to [http://localhost:8000/docs](http://localhost:8000/docs). You can interact with the API from this page
    * **Frontend Application**: Open the `frontend/index.html` file directly in your browser

---

## How to Run Tests

Ensure the application is running (from the `docker-compose up` command). Then, in a **new terminal**, run the following command to execute the test suite:

```sh
docker-compose exec backend pytest
```