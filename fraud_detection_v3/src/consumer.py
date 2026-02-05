import json
import logging
import requests
import os
from confluent_kafka import Consumer

# --- CONFIGURATION ---
# If running locally, we hit localhost:8000
# If running inside Docker later, we would use http://inference-service:8000
API_URL = os.getenv("INFERENCE_API_URL", "http://localhost:8000/predict")

# Kafka Config
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'fraud-detector-group-1',  # Consumer Group ID
    'auto.offset.reset': 'earliest'        # Start from beginning if no offset is found
}

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
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
                    source = prediction.get("source", "model")
                    
                    if is_fraud:
                        # 🚨 FRAUD ALERT VISUAL 🚨
                        print(f"\n🚨🚨 FRAUD DETECTED! 🚨🚨")
                        print(f"ID: {tx_id}")
                        print(f"Confidence: {prob:.4f}")
                        print(f"Source: {source}")
                        print("-" * 30 + "\n")
                    else:
                        # Normal log
                        logger.info(f"✅ Legit (ID: {tx_id[-6:]}...) | Risk: {prob:.4f} | Src: {source}")
                        
            except Exception as e:
                logger.error(f"Processing error: {e}")

    except KeyboardInterrupt:
        logger.info("🛑 Stopping Consumer...")
    finally:
        consumer.close()