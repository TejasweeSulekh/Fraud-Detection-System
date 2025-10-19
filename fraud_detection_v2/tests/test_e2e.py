# tests/test_e2e.py

import os
import json
import pytest
import requests
import asyncio
import websockets
import uuid
import time
from datetime import datetime
import pytest_asyncio

# --- Configuration ---
API_HOST = os.environ.get("API_HOST", "transaction-api")
API_PORT = os.environ.get("API_PORT", "8000")
API_URL = f"http://{API_HOST}:{API_PORT}"
WS_URL = f"ws://{API_HOST}:{API_PORT}/ws"

# Timeout for the WebSocket to receive a message
E2E_TIMEOUT = 10.0
# Timeout for the entire test, MUST be longer than the API wait time
TEST_TIMEOUT = 65.0 
# Timeout for the API to start
API_WAIT_TIMEOUT = 60.0


# --- =================== FIX =================== ---
# This helper function was accidentally deleted in the
# previous edit. It is now back in the global scope.

def post_transaction(data):
    """
    Helper function to post a new transaction.
    """
    try:
        response = requests.post(f"{API_URL}/transaction", json=data)
        response.raise_for_status() # Fail test if status is 4xx or 5xx
        return response
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Could not post transaction: {e}")
# --- ================= END OF FIX ================= ---


# --- Pytest Fixtures ---

@pytest.fixture(scope="session")
def wait_for_api():
    """
    Waits for the transaction-api to be online before running any tests.
    """
    start_time = time.time()
    
    print(f"\nWaiting for API at {API_URL}/docs ...")
    while time.time() - start_time < API_WAIT_TIMEOUT:
        try:
            response = requests.get(f"{API_URL}/docs")
            if response.status_code == 200:
                print(f"API is online after {time.time() - start_time:.2f} seconds.")
                return
        except requests.exceptions.ConnectionError:
            time.sleep(2)  # Wait 2 seconds before retrying
    
    pytest.fail(f"Could not connect to API at {API_URL} after {API_WAIT_TIMEOUT} seconds.")


@pytest_asyncio.fixture(scope="function")
async def websocket_listener(wait_for_api):
    """
    Fixture to connect to the WebSocket and listen for one message.
    It depends on 'wait_for_api' to ensure the server is ready.
    """
    message_queue = asyncio.Queue()

    async def listen(queue):
        try:
            async with websockets.connect(WS_URL) as websocket:
                message = await websocket.recv()
                await queue.put(json.loads(message))
        except Exception as e:
            await queue.put(e)

    loop = asyncio.get_running_loop()
    listener_task = loop.create_task(listen(message_queue))
    
    yield message_queue
    
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass


# --- =================== TESTS =================== ---

@pytest.mark.timeout(TEST_TIMEOUT)
def test_api_rejects_invalid_transaction(wait_for_api):
    """
    Tests that the API returns a 422 Validation Error for bad data.
    This test now shares the 'wait_for_api' fixture.
    """
    print("Testing for 422 Validation Error...")
    
    bad_tx = {
        "user_id": f"test-user-{uuid.uuid4()}",
        "merchant_id": "test-merchant",
        "timestamp": datetime.now().isoformat()
    }

    try:
        response = requests.post(f"{API_URL}/transaction", json=bad_tx)
        assert response.status_code == 422
        response_json = response.json()
        assert "detail" in response_json
        assert response_json["detail"][0]["msg"] == "Field required"
        print("Test passed: API correctly returned 422.")
        
    except requests.exceptions.RequestException as e:
        pytest.fail(f"API connection failed: {e}")


@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.asyncio
async def test_full_pipeline_fraudulent_transaction(websocket_listener):
    """
    The main E2E test for a FRAUDULENT transaction.
    """
    print("Testing full pipeline (FRAUD)...")
    
    test_tx = {
        "user_id": f"test-user-{uuid.uuid4()}",
        "amount": 5000.0,
        "merchant_id": "test-merchant",
        "timestamp": datetime.now().isoformat()
    }

    loop = asyncio.get_running_loop()
    # This line will now work
    post_response = await loop.run_in_executor(None, post_transaction, test_tx)
    assert post_response.status_code == 200
    assert post_response.json()["status"] == "Transaction sent for processing"

    try:
        result = await asyncio.wait_for(websocket_listener.get(), timeout=E2E_TIMEOUT)
        if isinstance(result, Exception):
            pytest.fail(f"WebSocket listener failed: {result}")
            
    except asyncio.TimeoutError:
        pytest.fail(f"Test timed out waiting for WebSocket message.")

    print(f"Received E2E test result: {result}")
    assert result["is_fraud"] == True
    assert result["fraud_score"] == 0.9
    assert result["transaction"]["user_id"] == test_tx["user_id"]
    print("Test passed: Fraudulent transaction correctly identified.")


@pytest.mark.timeout(TEST_TIMEOUT)
@pytest.mark.asyncio
async def test_full_pipeline_non_fraudulent_transaction(websocket_listener):
    """
    The main E2E test for a NON-FRAUDULENT transaction.
    """
    print("Testing full pipeline (NON-FRAUD)...")
    
    test_tx = {
        "user_id": f"test-user-{uuid.uuid4()}",
        "amount": 50.0,
        "merchant_id": "test-merchant",
        "timestamp": datetime.now().isoformat()
    }

    loop = asyncio.get_running_loop()
    # This line will now work
    post_response = await loop.run_in_executor(None, post_transaction, test_tx)
    assert post_response.status_code == 200
    assert post_response.json()["status"] == "Transaction sent for processing"

    try:
        result = await asyncio.wait_for(websocket_listener.get(), timeout=E2E_TIMEOUT)
        if isinstance(result, Exception):
            pytest.fail(f"WebSocket listener failed: {result}")
            
    except asyncio.TimeoutError:
        pytest.fail(f"Test timed out waiting for WebSocket message.")

    print(f"Received E2E test result: {result}")
    assert result["is_fraud"] == False
    assert result["fraud_score"] == 0.1
    assert result["transaction"]["user_id"] == test_tx["user_id"]
    print("Test passed: Non-fraudulent transaction correctly identified.")