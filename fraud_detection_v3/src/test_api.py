import requests

# The URL of your dockerized inference service
url = "http://localhost:8000/predict"

# A fake transaction payload (matches the features your model expects)
payload = {
    "features": [
        0.0,    # Time
        -1.35,  # V1
        1.25,   # V2
        -0.5,   # V3
        0.5,    # V4
        -0.5,   # V5
        0.5,    # V6
        0.2,    # V7
        -0.1,   # V8
        0.0,    # V9
        0.1,    # V10
        -0.5,   # V11
        0.0,    # V12
        0.5,    # V13
        -0.3,   # V14
        0.2,    # V15
        0.1,    # V16
        -0.5,   # V17
        0.0,    # V18
        0.5,    # V19
        -0.2,   # V20
        0.1,    # V21
        -0.5,   # V22
        0.0,    # V23
        0.1,    # V24
        -0.2,   # V25
        0.1,    # V26
        0.5,    # V27
        -0.1,   # V28
        50.0    # Amount
    ]
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Prediction: {response.json()}")
except Exception as e:
    print(f"Error: {e}")