# transaction_api/app/main.py

import os
import json
import logging
import asyncio
import time
import functools
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TRANSACTIONS_TOPIC = os.environ.get("TRANSACTIONS_TOPIC", "transactions")
RESULTS_TOPIC = os.environ.get("RESULTS_TOPIC", "transaction-results")

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI()
producer = None # Will be initialized on startup

# --- Pydantic Model ---
class Transaction(BaseModel):
    user_id: str
    amount: float
    merchant_id: str
    timestamp: str

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# --- API Endpoints ---
@app.post("/transaction")
async def create_transaction(transaction: Transaction):
    if not producer:
        logger.error("Kafka producer is not available.")
        return {"error": "Kafka producer not available"}
    try:
        # The producer object itself is thread-safe
        producer.send(TRANSACTIONS_TOPIC, transaction.dict())
        producer.flush() # flush is blocking, let's run it in a thread
        # await asyncio.to_thread(producer.flush) # Even better, but simple flush is ok
        return {"status": "Transaction sent for processing"}
    except Exception as e:
        logger.error(f"Failed to send transaction to Kafka: {e}")
        return {"error": "Failed to send transaction"}

# Serve the frontend
app.mount("/frontend", StaticFiles(directory="/app/frontend", html=True), name="frontend")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info("Client connected to WebSocket.")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from WebSocket.")


# --- BLOCKING CONSUMER FUNCTION ---
# This function is NOT async. It's designed to run in a separate thread.
def blocking_consumer_loop(loop: asyncio.AbstractEventLoop, manager: ConnectionManager):
    consumer = None
    retries = 10
    while retries > 0 and consumer is None:
        try:
            # This is a blocking call
            consumer = KafkaConsumer(
                RESULTS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id="transaction-results-group",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest'
            )
            logger.info("Result consumer successfully connected to Kafka.")
        except NoBrokersAvailable:
            logger.error(f"Could not connect result consumer to Kafka. Retrying in 5 seconds... ({retries} retries left)")
            retries -= 1
            time.sleep(5) # Use blocking sleep (it's OK, we are in a thread)

    if not consumer:
        logger.critical("Could not connect to Kafka for consuming results. Aborting consumer thread.")
        return

    try:
        # This 'for' loop is also blocking
        for message in consumer:
            logger.info(f"Received result: {message.value}")
            
            # We are in a thread, so we can't 'await'
            # We must safely schedule the async broadcast on the main event loop
            broadcast_task = manager.broadcast(json.dumps(message.value))
            asyncio.run_coroutine_threadsafe(broadcast_task, loop)
            
    except Exception as e:
        logger.error(f"An error occurred while consuming results: {e}")
    finally:
        consumer.close()
        logger.info("Result consumer thread shutting down.")


# --- FULLY NON-BLOCKING STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    global producer
    global manager
    loop = asyncio.get_event_loop()

    # --- 1. Connect Producer in a Thread ---
    def connect_producer():
        # This is a local, blocking function
        prod = None
        retries = 10
        while retries > 0 and prod is None:
            try:
                prod = KafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                logger.info("Successfully connected to Kafka Producer.")
            except NoBrokersAvailable:
                logger.error(f"Could not connect to Kafka Producer. Retrying in 5 seconds... ({retries} retries left)")
                retries -= 1
                time.sleep(5) # Blocking sleep
        return prod

    # await asyncio.to_thread() runs the blocking function in a thread
    # and waits for it without blocking the main event loop.
    producer = await asyncio.to_thread(connect_producer)

    if producer is None:
        logger.critical("Could not connect to Kafka Producer after multiple retries. API will not be able to send messages.")

    # --- 2. Run Consumer Loop in Background Thread ---
    
    # We use functools.partial to pass arguments to the blocking function
    consumer_task = functools.partial(blocking_consumer_loop, loop, manager)
    
    # loop.run_in_executor() runs the function in a thread pool
    # and does NOT wait for it. This lets startup finish.
    loop.run_in_executor(None, consumer_task)
    
    logger.info("FastAPI app startup complete.")