import os
import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from kafka import KafkaProducer, KafkaConsumer
import time

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TRANSACTIONS_TOPIC = os.getenv('TRANSACTIONS_TOPIC', 'transactions')
RESULTS_TOPIC = os.getenv('RESULTS_TOPIC', 'transaction-results')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI()
producer = None
consumer = None

# --- Kafka Connection Handling ---
async def get_kafka_producer():
    """Retry connecting to Kafka until successful."""
    global producer
    while producer is None:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info("Successfully connected to Kafka Producer.")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka Producer: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
    return producer

async def get_kafka_consumer():
    """Retry connecting to Kafka until successful."""
    global consumer
    while consumer is None:
        try:
            consumer = KafkaConsumer(
                RESULTS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest', # Start from the latest message
                group_id='transaction-results-group'
            )
            logger.info("Successfully connected to Kafka Consumer.")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka Consumer: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
    return consumer


@app.on_event("startup")
async def startup_event():
    """On startup, initialize Kafka connections."""
    app.state.kafka_producer = await get_kafka_producer()
    app.state.kafka_consumer = await get_kafka_consumer()
    # Start the consumer in the background
    asyncio.create_task(consume_results())


# --- API Endpoints ---
@app.post("/transaction")
async def send_transaction(request: Request):
    """
    Receives transaction data and sends it to the 'transactions' Kafka topic.
    """
    transaction_data = await request.json()
    transaction_data['timestamp'] = int(time.time() * 1000) # Add timestamp
    
    producer = app.state.kafka_producer
    producer.send(TRANSACTIONS_TOPIC, value=transaction_data)
    producer.flush() # Ensure message is sent
    
    logger.info(f"Published transaction: {transaction_data}")
    return {"status": "Transaction sent for processing"}

# --- WebSocket Handling for Real-time Results ---
clients = set()

async def consume_results():
    """
    Background task to consume from the results topic and broadcast to WebSocket clients.
    """
    consumer = app.state.kafka_consumer
    logger.info("Result consumer background task started.")
    for message in consumer:
        logger.info(f"Received result: {message.value}")
        # Broadcast to all connected WebSocket clients
        for client in list(clients):
            try:
                await client.send_text(json.dumps(message.value))
            except Exception as e:
                logger.warning(f"Failed to send message to client, removing: {e}")
                clients.remove(client)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles WebSocket connections for real-time fraud detection results.
    """
    await websocket.accept()
    clients.add(websocket)
    logger.info("New WebSocket client connected.")
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except Exception:
        logger.info("WebSocket client disconnected.")
    finally:
        clients.remove(websocket)
