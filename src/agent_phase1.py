import os
import json
import requests
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Import your existing database setup
from src.database import SessionLocal, PredictionLog

load_dotenv()

# We default to localhost assuming you are running this script outside the cluster for testing,
# but your cluster ports (5432 for Postgres, 8000 for FastAPI) need to be forwarded/accessible.
INFERENCE_API_URL = os.getenv("API_URL", "http://localhost:8000")

# --- 1. The Real Explainability Tool ---
@tool
def analyze_shap_values(transaction_id: str) -> str:
    """
    Explains why a transaction was flagged as fraud. 
    It retrieves the raw transaction data from the database and queries the ML model 
    for the SHAP feature importance.
    Always use this when asked to investigate or explain a specific transaction.
    """
    print(f"\n[SYSTEM LOG] 🔍 Fetching database record for: {transaction_id}...")
    
    session = SessionLocal()
    try:
        # 1. Fetch the stored input data from Postgres
        record = session.query(PredictionLog).filter(PredictionLog.transaction_id == transaction_id).first()
        
        if not record:
            return f"Error: Transaction {transaction_id} not found in the database."
            
        if not record.input_data:
             return f"Error: No raw input features were stored for {transaction_id}."
             
        transaction_data = json.loads(record.input_data)
        
        # 2. Call the FastAPI /explain endpoint
        print(f"[SYSTEM LOG] 🧠 Sending data to {INFERENCE_API_URL}/explain for SHAP analysis...")
        response = requests.post(f"{INFERENCE_API_URL}/explain", json=transaction_data, timeout=5)
        
        if response.status_code == 200:
            explanation = response.json()
            status = "FRAUD" if record.is_fraud else "LEGITIMATE"
            features = explanation.get('top_contributing_features', {})
            
            # We return a formatted string to the LLM so it can easily read the context
            return (
                f"Model Prediction: {status} (Risk Score: {record.fraud_probability:.4f})\n"
                f"Top Contributing Features (SHAP values): {json.dumps(features)}"
            )
        else:
            return f"API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"System Error: {str(e)}"
        print(f"\n[DEBUG - CAUGHT EXCEPTION]: {error_msg}\n")
        return error_msg
    finally:
        session.close()

def run_investigation():
    print("Initializing Agentic AI Investigator...")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    tools = [analyze_shap_values]

    # --- 2. The LangGraph Agent ---
    agent_executor = create_react_agent(llm, tools)
    
    # We need a valid transaction ID from your database to test this.
    # Replace this with an actual ID from your Streamlit dashboard!
    test_tx_id = input("\nEnter a Transaction ID from your dashboard to investigate: ")

    print(f"\nStarting Investigation for {test_tx_id}...\n")
    
    # --- 3. The Invocation ---
    prompt = f"""
    Investigate transaction {test_tx_id}. 
    Use your tools to find out if it was flagged as fraud, and write a short, 
    professional 2-sentence summary explaining WHICH specific features caused this decision.
    """
    
    result = agent_executor.invoke({"messages": [("user", prompt)]})
    
    print("\n--- FINAL AGENT REPORT ---")
    final_message = result["messages"][-1].content
    if isinstance(final_message, list):
        print(final_message[0].get("text", "No text found"))
    else:
        print(final_message)

if __name__ == "__main__":
    run_investigation()