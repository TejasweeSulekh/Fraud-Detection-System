import os
import json
import random
import logging
import time
from kafka import KafkaConsumer, KafkaProducer

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TRANSACTIONS_TOPIC = os.getenv('TRANSACTIONS_TOPIC', 'transactions')
RESULTS_TOPIC = os.getenv('RESULTS_TOPIC', 'transaction-results')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Fraud Detection Logic ---
def detect_fraud(transaction: dict) -> dict:
    """
    A placeholder for your fraud detection logic.
    For V2, we'll simulate it with a random score.
    
    In a real system, this would involve:
    - Checking against rule-based systems.
    - Querying historical data.
    - Calling a machine learning model.
    """
    # Simulate processing time
    time.sleep(random.uniform(0.1, 0.5))

    # Simulate a fraud score
    fraud_score = random.uniform(0.0, 1.0)
    
    transaction['fraud_score'] = round(fraud_score, 4)
    if fraud_score > 0.85:
        transaction['is_fraud'] = True
        transaction['decision'] = "BLOCK"
    else:
        transaction['is_fraud'] = False
        transaction['decision'] = "APPROVE"
        
    return transaction


# --- Main Application Logic ---
def main():
    """
    Connects to Kafka, consumes transactions, processes them, and publishes results.
    """
    consumer = None
    producer = None

    # Retry connecting to Kafka until successful
    while consumer is None:
        try:
            consumer = KafkaConsumer(
                TRANSACTIONS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='fraud-detector-group'
            )
            logger.info("Fraud Detector connected to Kafka Consumer.")
        except Exception as e:
            logger.error(f"Failed to connect Consumer: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            
    while producer is None:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info("Fraud Detector connected to Kafka Producer.")
        except Exception as e:
            logger.error(f"Failed to connect Producer: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    logger.info("Fraud detector service started. Waiting for transactions...")
    for message in consumer:
        transaction_data = message.value
        logger.info(f"Processing transaction: {transaction_data}")
        
        # Apply fraud detection logic
        result = detect_fraud(transaction_data)
        
        # Publish the result to the results topic
        producer.send(RESULTS_TOPIC, value=result)
        producer.flush()
        logger.info(f"Published result: {result}")

if __name__ == "__main__":
    main()
