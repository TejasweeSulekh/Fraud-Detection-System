import json
import time
import random
import uuid
import logging
from confluent_kafka import Producer
import socket
import os

# Setup Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("Producer")

# --- CONFIGURATION ---
KAFKA_BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Kafka Configuration
conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'client.id': socket.gethostname()
}

producer = Producer(conf)
topic = "transaction_stream"

def delivery_callback(err, msg):
    """Callback to verify if message was sent successfully"""
    if err:
        logger.error(f"❌ Message failed delivery: {err}")
    else:
        # msg.key() returns bytes, so we decode for printing
        key = msg.key().decode('utf-8') if msg.key() else "None"
        logger.debug(f"✅ Sent: {key} to partition {msg.partition()}")

def generate_fake_transaction():
    """Generates a dict matching the model schema"""
    tx = {
        "transaction_id": str(uuid.uuid4()),
        "Time": time.time(),
        "Amount": round(random.uniform(10.0, 5000.0), 2)
    }
    # Add V1-V28 features
    for i in range(1, 29):
        tx[f"V{i}"] = random.uniform(-2.0, 2.0)
    return tx

if __name__ == "__main__":
    logger.info("🚀 Starting Transaction Producer...")
    
    try:
        while True:
            # 1. Generate Data
            tx = generate_fake_transaction()
            
            # 2. Serialize to JSON
            value_json = json.dumps(tx)
            key = tx["transaction_id"] # Use ID as key for ordering (optional here)

            # 3. Send to Kafka
            # trigger callback to keep buffer clean
            producer.poll(0) 
            producer.produce(
                topic=topic, 
                key=key, 
                value=value_json, 
                callback=delivery_callback
            )
            
            # 4. Wait a bit (Simulate traffic)
            time.sleep(0.5) # 2 transactions per second

    except KeyboardInterrupt:
        logger.info("🛑 Stopping Producer...")
    finally:
        producer.flush() # Ensure all messages are sent before exiting