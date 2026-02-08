import requests
import random
import uuid

# URL of the API (localhost:8000 because we access it from outside Docker)
url = "http://localhost:8000/predict"

# Generate a fake transaction dictionary matching the Pydantic schema
# We create a dictionary with Time, V1..V28, and Amount
fake_transaction = {
    "transaction_id": str(uuid.uuid4()),
    "Time": 100.0,
    "Amount": 500.0
}
# Add V1 through V28
for i in range(1, 29):
    fake_transaction[f"V{i}"] = random.uniform(-1.0, 1.0)

# The API expects a LIST of transactions
payload = [fake_transaction]

try:
    print("Sending request to API...")
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("✅ Success!")
        print("Response:", response.json())
    else:
        print(f"❌ Failed: {response.status_code}")
        print("Detail:", response.text)

except Exception as e:
    print(f"❌ Connection Error: {e}")