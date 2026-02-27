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

def generate_fake_transaction():
    tx = {
        "transaction_id": str(uuid.uuid4()),
        "Time": time.time(),
        "Amount": round(random.uniform(10.0, 5000.0), 2)
    }
    for i in range(1, 29):
        tx[f"V{i}"] = random.uniform(-2.0, 2.0)
    return tx

if __name__ == "__main__":
    logger.info("Starting Transaction Producer...")
    
    try:
        while True:
            tx = generate_fake_transaction()
            value_json = json.dumps(tx)
            key = tx["transaction_id"] 

            producer.poll(0) 
            producer.produce(
                topic=topic, 
                key=key, 
                value=value_json, 
                callback=delivery_callback
            )
            
            time.sleep(5) 

    except KeyboardInterrupt:
        logger.info("Stopping Producer...")
    finally:
        producer.flush()