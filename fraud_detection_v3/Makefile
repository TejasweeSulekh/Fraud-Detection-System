# Makefile

.PHONY: up down restart logs clean producer consumer

# 1. Start the entire infrastructure (The "One Click" command)
up:
	docker-compose up -d --build
	@echo "🚀 System is starting! Waiting for services..."
	@sleep 10
	@echo "✅ Infrastructure is ready (API, Kafka, Redis, Postgres)."

# 2. Stop everything
down:
	docker-compose down

# 3. View Logs for the API
logs:
	docker logs -f fraud-inference-service

# 4. Run the Consumer (requires local environment setup)
consumer:
	python src/consumer.py

# 5. Run the Producer (requires local environment setup)
producer:
	python src/producer.py

# 6. Check the Database content
check-db:
	docker exec -it postgres_db psql -U fraud_user -d fraud_db -c "SELECT transaction_id, is_fraud, fraud_probability FROM predictions ORDER BY timestamp DESC LIMIT 5;"

# 7. Clean up Docker junk (careful!)
clean:
	docker-compose down -v
	docker system prune -f