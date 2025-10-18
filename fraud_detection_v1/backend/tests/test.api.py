import requests

# The base URL for our running API
BASE_URL = "http://localhost:8000"

def test_health_check():
    """Tests the /health endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_and_get_transactions():
    """
    Tests creating a legitimate transaction and then
    verifying it appears in the /transactions list.
    """
    # 1. Create a legitimate transaction
    tx_payload_legit = {
        "amount": 125.50,
        "merchant": "Test Restaurant",
        "location": "Chicago"
    }
    response_post = requests.post(f"{BASE_URL}/transaction", json=tx_payload_legit)
    
    assert response_post.status_code == 200
    post_data = response_post.json()
    assert post_data["is_fraud"] == False
    assert post_data["amount"] == tx_payload_legit["amount"]
    
    # 2. Create a fraudulent transaction
    tx_payload_fraud = {
        "amount": 3000.00,
        "merchant": "Suspicious Electronics",
        "location": "Offshore"
    }
    response_post_fraud = requests.post(f"{BASE_URL}/transaction", json=tx_payload_fraud)
    
    assert response_post_fraud.status_code == 200
    fraud_data = response_post_fraud.json()
    assert fraud_data["is_fraud"] == True
    assert fraud_data["fraud_reason"] == "Amount exceeds $1500"

    # 3. Get all transactions and check for our new ones
    response_get = requests.get(f"{BASE_URL}/transactions")
    assert response_get.status_code == 200
    get_data = response_get.json()
    
    assert isinstance(get_data, list)
    assert len(get_data) >= 2 # Check that at least our two test transactions are there
    
    # Check that the IDs from our created transactions are in the returned list
    created_ids = {post_data["id"], fraud_data["id"]}
    returned_ids = {tx["id"] for tx in get_data}
    assert created_ids.issubset(returned_ids)