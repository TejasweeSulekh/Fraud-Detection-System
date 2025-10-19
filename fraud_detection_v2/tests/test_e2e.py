import os
import json
import pytest
import requests
import asyncio
import websockets
import uuid
from datetime import datetime

# --- Configuration ---
# These must match the service names in docker-compose.yml
API_HOST = os.environ.get("API_HOST", "transaction-api")
API_PORT = os.environ.get("API_PORT", "8000")
API_URL = f"http://{API_HOST}:{API_PORT}"
WS_URL = f"ws://{API_HOST}:{API_PORT}/ws"

# Set a generous timeout (in seconds) for the test to wait for the WebSocket message
E2E_TIMEOUT = 10.0


# --- Pytest Fixtures ---

@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for our async test."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
@pytest.mark.asyncio
async def websocket_listener():
    """
    Fixture to connect to the WebSocket and listen for one message.
    This is a bit complex, but it's the right way to test WebSockets.
    """
    # We use an asyncio.Queue to safely pass the message
    # from the listening task to the main test task.
    message_queue = asyncio.Queue()

    async def listen(queue):
        try:
            async with websockets.connect(WS_URL) as websocket:
                # When connected, wait for the first message
                message = await websocket.recv()
                # Put the message in the queue for the test to retrieve
                await queue.put(json.loads(message))
        except Exception as e:
            # Put the exception in the queue so the test fails
            await queue.put(e)

    # Start the listener task in the background
    listener_task = asyncio.create_task(listen(message_queue))
    
    # Yield the queue (as the "listener") to the test
    yield message_queue
    
    # After the test is done, clean up
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass # Task cancellation is expected


# --- Helper Function ---

def post_transaction(data):
    """Helper to post a new transaction."""
    try:
        response = requests.post(f"{API_URL}/transaction", json=data)
        response.raise_for_status() # Fail test if status is 4xx or 5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Could not connect to API at {API_URL}. Is it running?\nError: {e}")


# --- Tests ---

@pytest.mark.timeout(10)
def test_api_service_is_online():
    """
    A simple "health check" to see if the transaction-api is reachable.
    """
    try:
        # Check the /docs endpoint as a health check
        response = requests.get(f"{API_URL}/docs")
        assert response.status_code == 200
    except requests.exceptions.ConnectionError:
        pytest.fail(f"Could not connect to {API_URL}. Check service name and port.")

@pytest.mark.timeout(E2E_TIMEOUT + 2) # Give 2 extra seconds
@pytest.mark.asyncio
async def test_full_transaction_pipeline_e2e(websocket_listener):
    """
    The main End-to-End test.
    1. Starts listening on the WebSocket (via the fixture).
    2. Submits a fraudulent transaction via HTTP.
    3. Waits to receive the result on the WebSocket.
    4. Asserts the result is correct.
    """
    
    # 1. Define a unique, fraudulent transaction
    test_tx = {
        "user_id": f"test-user-{uuid.uuid4()}",
        "amount": 5000.0, # This should be > 1000 to be fraud
        "merchant_id": "test-merchant",
        "timestamp": datetime.now().isoformat()
    }

    # 2. Submit the transaction via HTTP
    # (We run this blocking 'requests' call in an async-friendly way)
    loop = asyncio.get_running_loop()
    post_response = await loop.run_in_executor(None, post_transaction, test_tx)
    assert post_response["status"] == "Transaction sent for processing"

    # 3. Wait for the result from the WebSocket
    try:
        result = await asyncio.wait_for(websocket_listener.get(), timeout=E2E_TIMEOUT)
        
        # If we get an exception from the queue, fail the test
        if isinstance(result, Exception):
            pytest.fail(f"WebSocket listener failed: {result}")
            
    except asyncio.TimeoutError:
        pytest.fail(f"Test timed out after {E2E_TIMEOUT}s waiting for WebSocket message.")

    # 4. Assert the result is correct
    assert result["is_fraud"] == True
    assert result["fraud_score"] == 0.9
    assert result["transaction"]["user_id"] == test_tx["user_id"]
    assert result["transaction"]["amount"] == test_tx["amount"]