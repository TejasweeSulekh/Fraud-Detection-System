import os
import json
import pytest
import requests
import asyncio
import websockets
import uuid
import time
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
def wait_for_api():
    """
    Waits for the transaction-api to be online before running any tests.
    """
    start_time = time.time()
    timeout = 60  # Wait up to 60 seconds
    
    print(f"Waiting for API at {API_URL}/docs ...")
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{API_URL}/docs")
            if response.status_code == 200:
                print(f"API is online!")
                return
        except requests.exceptions.ConnectionError:
            time.sleep(2)  # Wait 2 seconds before retrying
    
    pytest.fail(f"Could not connect to API at {API_URL} after {timeout} seconds.")


@pytest.fixture(scope="module")
@pytest.mark.asyncio
async def websocket_listener(wait_for_api):
    """
    Fixture to connect to the WebSocket and listen for one message.
    This fixture now depends on 'wait_for_api' to ensure the API is up.
    """
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
    
    yield message_queue
    
    # After the test is done, clean up
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass  # Task cancellation is expected


# --- Tests ---

# We no longer need the separate test_api_service_is_online()
# because our wait_for_api fixture handles it.

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
    def post_transaction(data):
        try:
            response = requests.post(f"{API_URL}/transaction", json=data)
            response.raise_for_status() # Fail test if status is 4xx or 5xx
            return response.json()
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Could not post transaction: {e}")

    loop = asyncio.get_running_loop()
    post_response = await loop.run_in_executor(None, post_transaction, test_tx)
    assert post_response["status"] == "Transaction sent for processing"

    # 3. Wait for the result from the WebSocket
    try:
        result = await asyncio.wait_for(websocket_listener.get(), timeout=E2E_TIMEOUT)
        
        if isinstance(result, Exception):
            pytest.fail(f"WebSocket listener failed: {result}")
            
    except asyncio.TimeoutError:
        pytest.fail(f"Test timed out after {E2E_TIMEOUT}s waiting for WebSocket message.")

    # 4. Assert the result is correct
    print(f"Received E2E test result: {result}")
    assert result["is_fraud"] == True
    assert result["fraud_score"] == 0.9
    assert result["transaction"]["user_id"] == test_tx["user_id"]
    assert result["transaction"]["amount"] == test_tx["amount"]