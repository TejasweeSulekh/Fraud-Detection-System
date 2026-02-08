import json
import logging
import requests
import os
from confluent_kafka import Consumer

# --- CONFIGURATION ---
# If running locally, we hit localhost:8000
# If running inside Docker later, we would use http://inference-service:8000
KAFKA_BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
API_URL = os.getenv("INFERENCE_API_URL", "http://localhost:8000/predict")
# Kafka Config
conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'fraud-detector-group-1',
    'auto.offset.reset': 'earliest'
}

# Setup Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("Consumer")

def process_transaction(transaction_data):
    """
    Sends the transaction to the REST API for prediction.
    """
    try:
        # The API expects a LIST of transactions
        payload = [transaction_data]
        
        # Call the API
        response = requests.post(API_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            result = response.json()["batch_results"][0]
            return result
        else:
            logger.error(f"API Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to call API: {e}")
        return None

if __name__ == "__main__":
    logger.info("👀 Starting Fraud Detection Consumer...")
    
    consumer = Consumer(conf)
    consumer.subscribe(['transaction_stream'])

    try:
        while True:
            # 1. Poll for messages (wait max 1.0s)
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue

            # 2. Decode Message
            try:
                tx_data = json.loads(msg.value().decode('utf-8'))
                tx_id = tx_data.get("transaction_id", "Unknown")
                
                # 3. Get Prediction
                prediction = process_transaction(tx_data)
                
                if prediction:
                    # 4. Handle Result
                    is_fraud = prediction["is_fraud"]
                    prob = prediction["fraud_probability"]
                    tx_id = tx_data.get("transaction_id", "Unknown")
                    source = prediction.get("source", "model")
                    
                    if is_fraud:
                        # 🚨 FRAUD ALERT VISUAL 🚨
                        logger.warning(f"🚨 FRAUD DETECTED! ID: {tx_id} | Confidence: {prob:.4f}")
                    else:
                        # Normal log
                        logger.debug(f"✅ Legit (ID: {tx_id[-6:]}...) | Risk: {prob:.4f}")
                        
            except Exception as e:
                logger.error(f"Processing error: {e}")

    except KeyboardInterrupt:
        logger.info("🛑 Stopping Consumer...")
    finally:
        consumer.close()