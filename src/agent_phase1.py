import os
import json
import requests
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from sqlalchemy import text # Needed for the custom pgvector SQL query
from pydantic import BaseModel, Field
from typing import List, Optional
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

class InvestigationReport(BaseModel):
    transaction_id: str = Field(description="The ID of the transaction being investigated.")
    is_fraud: bool = Field(description="True if the model flagged it as fraud, False otherwise.")
    risk_score: Optional[float] = Field(description="The numeric risk score/probability from the model, if available.")
    key_drivers: List[str] = Field(description="List of the top 3-5 feature names that drove the decision (e.g., ['V20', 'V16']).")
    historical_context: str = Field(description="A brief summary of whether similar historical transactions were found and their status. Note if the tool failed.")
    executive_summary: str = Field(description="A professional, 2-3 sentence final verdict explaining the flag.")
    data_complete: bool = Field(description="False if any tools failed (like network errors or quota limits), True if all tools succeeded.")

def run_investigation(transaction_id: str) -> dict:
    """Runs the agent and returns a structured dictionary for the API."""
    print(f"\n[SYSTEM LOG] 🚀 Starting Investigation for {transaction_id}...")
    
    try:
        # 1. We are officially back to the working 2.5 model
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        tools = [analyze_shap_values, search_historical_fraud]

        agent_executor = create_react_agent(llm, tools)
        
        prompt = f"""
        Investigate transaction {transaction_id}. 
        1. Use the SHAP tool to find out WHY the model flagged it.
        2. Use the historical search tool to see if this pattern has happened before.
        Write a short, professional 3-sentence summary combining both insights.
        """
        
        # 2. Run the Agent
        for step_event in agent_executor.stream({"messages": [("user", prompt)]}):
            pass # Silenced for API speed
            
        final_state = list(step_event.values())[0]
        raw_final_message = final_state["messages"][-1].content
        if isinstance(raw_final_message, list):
            raw_final_message = raw_final_message[0].get("text", raw_final_message)

        print("\n[SYSTEM LOG] 📝 Structuring the agent's report...")
        
        # 3. The Formatter Brain
        formatter_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        structured_llm = formatter_llm.with_structured_output(InvestigationReport)
        
        formatting_prompt = f"""
        Extract info from this report and format it strictly.
        Target Transaction ID: {transaction_id}
        Raw Report: {raw_final_message}
        """
        
        final_structured_report = structured_llm.invoke(formatting_prompt)
        print("[SYSTEM LOG] ✅ Formatter succeeded.")
        
        return json.loads(final_structured_report.model_dump_json())
        
    except Exception as e:
        # --- THE MAGIC BYPASS ---
        # If the LLM throws a Quota error, we catch it and return a simulated payload
        print(f"\n[SYSTEM LOG] ⚠️ Agent or Quota Failed. Returning UI Simulation Data.\nError: {e}")
        
        simulated_report = {
            "transaction_id": transaction_id,
            "is_fraud": True,
            "risk_score": 0.99,
            "key_drivers": ["V16 (Simulated)", "Amount (Simulated)"],
            "historical_context": "Simulated Data: The API quota is currently exhausted, so this is mock data to verify the Streamlit UI.",
            "executive_summary": "SIMULATED REPORT: The Streamlit frontend and FastAPI backend are perfectly connected! Once the Gemini quota resets in a few hours, the real agent will seamlessly take over this pipeline.",
            "data_complete": False
        }
        return simulated_report