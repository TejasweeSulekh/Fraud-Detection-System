import os
import json
import logging
import time
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TRANSACTIONS_TOPIC = os.environ.get("TRANSACTIONS_TOPIC", "transactions")
RESULTS_TOPIC = os.environ.get("RESULTS_TOPIC", "transaction-results")

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_to_kafka(retries=10, delay=5):
    """Attempt to connect to Kafka with retries."""
    while retries > 0:
        try:
            consumer = KafkaConsumer(
                TRANSACTIONS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id="fraud-detector-group",
                auto_offset_reset='earliest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info("Fraud detector successfully connected to Kafka.")
            return consumer, producer
        except NoBrokersAvailable:
            logger.error(f"Could not connect to Kafka. Retrying in {delay} seconds... ({retries} retries left)")
            retries -= 1
            time.sleep(delay)
    logger.critical("Could not connect to Kafka after multiple retries. Aborting.")
    return None, None


def run_detector():
    """Continuously consumes transactions, processes them, and produces results."""
    consumer, producer = connect_to_kafka()
    if not consumer or not producer:
        return

    logger.info("Fraud detector is running and waiting for messages...")
    for message in consumer:
        try:
            data = message.value
            logger.info(f"Processing transaction: {data}")

            # Basic fraud detection logic
            amount = data.get('amount', 0)
            if not isinstance(amount, (int, float)):
                 raise TypeError("Amount must be a number.")

            if amount > 1000:
                fraud_score = 0.9
                is_fraud = True
            else:
                fraud_score = 0.1
                is_fraud = False

            # Prepare the result message
            result = {
                "transaction": data,
                "fraud_score": fraud_score,
                "is_fraud": is_fraud
            }
            logger.info(f"Producing result: {result}")

            # Send the result to the results topic
            producer.send(RESULTS_TOPIC, result)
            producer.flush()

        except json.JSONDecodeError:
            logger.error(f"Could not decode message: {message.value}")
            continue
        except (KeyError, TypeError) as e:
            logger.error(f"Error processing message {message.value}: {e}")
            continue
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            continue


if __name__ == "__main__":
    run_detector()

