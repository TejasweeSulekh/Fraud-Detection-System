# import requests
# import time
# import sys

# # Configuration
# MLFLOW_URL = "http://localhost:5000"
# INFERENCE_URL = "http://localhost:8000"

# def check_service(name, url, retries=5):
#     """Pings a service URL to see if it is alive."""
#     print(f"Testing {name} at {url}...")
#     for i in range(retries):
#         try:
#             response = requests.get(url)
#             if response.status_code < 500: # Any 200-400 code means it's alive
#                 print(f"{name} is UP!")
#                 return True
#         except requests.exceptions.ConnectionError:
#             pass
        
#         print(f"   ...waiting for {name} ({i+1}/{retries})")
#         time.sleep(2)
    
#     print(f"{name} is DOWN.")
#     return False

# def check_prediction():
#     """Sends a dummy transaction to test end-to-end inference."""
#     print("\nTesting Model Inference...")
#     payload = {
#         "features": [0.0] * 30  # Dummy vector of 30 zeros
#     }
    
#     try:
#         response = requests.post(f"{INFERENCE_URL}/predict", json=payload)
#         if response.status_code == 200:
#             data = response.json()
#             print(f"Inference Successful! Prediction: {data}")
#             return True
#         else:
#             print(f"Inference Failed: {response.status_code} - {response.text}")
#             return False
#     except Exception as e:
#         print(f"Inference Error: {e}")
#         return False

# if __name__ == "__main__":
#     print("STARTING SYSTEM HEALTH CHECK...\n")
    
#     # 1. Check MLflow Server
#     mlflow_up = check_service("MLflow Server", MLFLOW_URL)
    
#     # 2. Check Inference API (Health endpoint)
#     # Note: We assume FastAPI has a default root or we check the docs/health
#     api_up = check_service("Inference API", f"{INFERENCE_URL}/docs") 

#     if mlflow_up and api_up:
#         # 3. Check if Model is actually working
#         prediction_up = check_prediction()
        
#         if prediction_up:
#             print("\nSYSTEM STATUS: GREEN (Ready for Phase 5)")
#             sys.exit(0)
    
#     print("\nSYSTEM STATUS: RED (Fix issues before proceeding)")
#     sys.exit(1)