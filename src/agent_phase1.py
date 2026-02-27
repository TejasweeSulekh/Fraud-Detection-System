import os
import json
import requests
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import text # Needed for the custom pgvector SQL query
import langchain
langchain.debug = True

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
        error_msg = f"System Error in analyze_shap_values: {str(e)}"
        print(f"\n[DEBUG - CAUGHT EXCEPTION]: {error_msg}\n")
        return error_msg
    finally:
        session.close()
        
# --- 2. The JIT Vector Search Tool ---
@tool
def search_historical_fraud(transaction_id: str) -> str:
    """
    Searches the database for past transactions that are mathematically/behaviorally 
    similar to the target transaction. Use this to find historical patterns of fraud.
    Always use this when investigating to see if this pattern has happened before.
    """
    print(f"\n[SYSTEM LOG] 🔎 Executing JIT Vector Search for: {transaction_id}...")
    session = SessionLocal()
    
    try:
        # 1. Fetch the target transaction's raw data
        target_record = session.query(PredictionLog).filter(PredictionLog.transaction_id == transaction_id).first()
        if not target_record:
            return f"Error: Transaction {transaction_id} not found."

        # 2. JIT Embedding Generation (The Lazy Load)
        vector_to_search = target_record.embedding
        
        if vector_to_search is None:
            print(f"[SYSTEM LOG] ⚙️ No embedding found for this ID. Generating on the fly...")
            embedder = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
            
            tx_data = json.loads(target_record.input_data)
            text_to_embed = f"Transaction amount: ${tx_data.get('Amount')}, Time: {tx_data.get('Time')}."
            
            # Generate the vector and save it back to the DB so we don't pay for it twice
            vector_to_search = embedder.embed_query(text_to_embed)
            target_record.embedding = vector_to_search
            session.commit()
        
        # 3. Vector Similarity Search (The pgvector Magic)
        print(f"[SYSTEM LOG] 📚 Searching vector database for similar historical patterns...")
        
        # We use <=> which calculates Cosine Distance (best for LLM embeddings)
        query = text("""
            SELECT transaction_id, is_fraud, amount, embedding <=> :target_vector AS distance
            FROM predictions
            WHERE transaction_id != :target_id AND embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT 3
        """)
        
        results = session.execute(query, {
            "target_vector": str(vector_to_search), 
            "target_id": transaction_id
        }).fetchall()

        if not results:
            return "No historical transactions with embeddings found to compare against."

        # 4. Format the context for the LLM to read
        report = "Historical Similar Transactions Found:\n"
        fraud_count = 0
        for row in results:
            status = "FRAUD" if row.is_fraud else "LEGITIMATE"
            if row.is_fraud: fraud_count += 1
            report += f"- ID: {row.transaction_id[:8]}... | Status: {status} | Amount: ${row.amount:.2f} | Cosine Distance: {row.distance:.4f}\n"
        
        report += f"\nConclusion: {fraud_count} out of the 3 most mathematically similar past transactions were flagged as {status}."
        return report

    except Exception as e:
        error_msg = f"Database/Search Error in search_historical_fraud: {str(e)}"
        print(f"\n[DEBUG - CAUGHT EXCEPTION]: {error_msg}\n")
        return error_msg
    finally:
        session.close()

def check_db_connection():
    """Fails fast if the database is not accessible before wasting LLM calls."""
    print("\n[SYSTEM LOG] 🔌 Checking database connection...")
    try:
        session = SessionLocal()
        session.execute(text("SELECT 1"))
        print("[SYSTEM LOG] ✅ Database connection successful.")
    except Exception as e:
        print(f"\n[FATAL ERROR] ❌ Database connection failed!")
        print(f"Did you forget to run 'kubectl port-forward'?\nError details: {e}\n")
        exit(1) # Stop the script entirely
    finally:
        session.close()

def run_investigation():
    print("Initializing Agentic AI Investigator...")
    
    # 1. Check connections before starting
    check_db_connection()
    
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    tools = [analyze_shap_values, search_historical_fraud]

    # --- 2. The LangGraph Agent ---
    agent_executor = create_react_agent(llm, tools)
    
    test_tx_id = input("\nEnter a Transaction ID from your dashboard to investigate: ")
    print(f"\nStarting Investigation for {test_tx_id}...\n")
    
    prompt = f"""
    Investigate transaction {test_tx_id}. 
    1. Use the SHAP tool to find out WHY the model flagged it.
    2. Use the historical search tool to see if this pattern has happened before.
    Write a short, professional 3-sentence summary combining both insights.
    """
    
    # --- 3. The Invocation (Using Stream for Debugging) ---
    print("\n--- AGENT THOUGHT PROCESS START ---")
    
    # .stream() yields the state of the agent after every single step
    for step_event in agent_executor.stream({"messages": [("user", prompt)]}):
        for node_name, node_data in step_event.items():
            print(f"\n>>> [AGENT STEP]: {node_name.upper()} <<<")
            
            # If the node is 'tools', print what the tool returned
            if node_name == "tools":
                latest_message = node_data["messages"][-1]
                print(f"Tool Output: {latest_message.content[:200]}...") # Print first 200 chars
                
    print("\n--- AGENT THOUGHT PROCESS END ---")
    print("\n--- FINAL AGENT REPORT ---")
    
    # Fetch the very last message from the final step's state
    final_state = list(step_event.values())[0]
    final_message = final_state["messages"][-1].content
    
    # Handle Gemini's list format gracefully
    if isinstance(final_message, list):
        print(final_message[0].get("text", final_message))
    else:
        print(final_message)

if __name__ == "__main__":
    run_investigation()