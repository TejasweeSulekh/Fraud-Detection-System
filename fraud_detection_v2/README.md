---
# Real-Time Fraud Detection System (V2.0)
This project (V2.0) refactors the fraud detection system into a scalable, real-time, event-driven architecture. It replaces the V1 monolithic backend and PostgreSQL database with a set of decoupled microservices that communicate using a Kafka message broker.

This new architecture is designed for high throughput and scalability. The `transaction-api` (the web server) is no longer responsible for fraud logic; it simply ingests transactions and serves the frontend. The `fraud-detector` service runs independently, allowing its logic to be updated or scaled without any downtime for the main API.
---