import json
import time
import random
import uuid
import logging
from confluent_kafka import Producer
import socket
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("Producer")

# --- CONFIGURATION ---
KAFKA_BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': socket.gethostname()
}

producer = Producer(conf)
topic = "transaction_stream"

def delivery_callback(err, msg):
    if err:
        logger.error(f"Message failed delivery: {err}")
    else:
        key = msg.key().decode('utf-8') if msg.key() else "None"
        logger.debug(f"Sent: {key} to partition {msg.partition()}")

def generate_fake_transaction(is_fraud=False):
    tx = {
        "transaction_id": str(uuid.uuid4()),
        "Time": time.time(),
    }

    if is_fraud:
        # Fraudulent: Higher amounts and extreme feature values
        tx["Amount"] = round(random.uniform(1000.0, 10000.0), 2)
        for i in range(1, 29):
            # Shift features to be outliers (e.g., -10 to -5 or 5 to 10)
            tx[f"V{i}"] = random.choice([random.uniform(-10, -5), random.uniform(5, 10)])
    else:
        # Legitimate: Normal amounts and stable features
        tx["Amount"] = round(random.uniform(10.0, 500.0), 2)
        for i in range(1, 29):
            tx[f"V{i}"] = random.uniform(-2.0, 2.0)
            
    return tx

if __name__ == "__main__":
    logger.info("Starting Transaction Producer with 10% Fraud Rate...")
    
    try:
        while True:
            # Determine if this specific transaction should be fraud (10% chance)
            is_fraud = random.random() < 0.10  
            
            tx = generate_fake_transaction(is_fraud=is_fraud)
            value_json = json.dumps(tx)
            
            if is_fraud:
                logger.warning(f"!!! Generating Fraudulent Transaction: {tx['transaction_id']} !!!")

            producer.poll(0) 
            producer.produce(
                topic=topic, 
                key=tx["transaction_id"], 
                value=value_json, 
                callback=delivery_callback
            )
            
            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Stopping Producer...")
    finally:
        producer.flush()