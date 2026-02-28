import os
import json
import requests
import logging
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.core.database import get_transaction_by_id, search_similar_transactions, update_transaction_embedding

logger = logging.getLogger("AgentTools")

# This matches the K8s service name and port
INFERENCE_API_URL = os.getenv("API_URL", "http://inference-service:8000")

@tool
def analyze_shap_values(transaction_id: str) -> str:
    """
    Explains why a transaction was flagged as fraud by querying the ML model 
    for the SHAP feature importance. Always use this when asked to investigate.
    """
    logger.info(f"Executing tool: analyze_shap_values for {transaction_id}")
    
    # 1. Clean data fetch using our new DB layer
    record = get_transaction_by_id(transaction_id)
    if not record:
        return f"Error: Transaction {transaction_id} not found in the database."
    if not record.get("input_data"):
         return f"Error: No raw input features were stored for {transaction_id}."
         
    try:
        # 2. Call the FastAPI /explain endpoint
        response = requests.post(f"{INFERENCE_API_URL}/explain", json=record["input_data"], timeout=5)
        
        if response.status_code == 200:
            explanation = response.json()
            status = "FRAUD" if record["is_fraud"] else "LEGITIMATE"
            features = explanation.get('top_contributing_features', {})
            
            return (
                f"Model Prediction: {status} (Risk Score: {record['fraud_probability']:.4f})\n"
                f"Top Contributing Features (SHAP values): {json.dumps(features)}"
            )
        else:
            return f"API Error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"System Error in analyze_shap_values: {str(e)}"

@tool
def search_historical_fraud(transaction_id: str) -> str:
    """
    Searches the database for past transactions that are mathematically/behaviorally 
    similar to the target transaction using vector similarity.
    """
    logger.info(f"Executing tool: search_historical_fraud for {transaction_id}")
    
    # 1. Fetch the target transaction
    record = get_transaction_by_id(transaction_id)
    if not record:
        return f"Error: Transaction {transaction_id} not found."

    # 2. JIT Embedding Generation
    vector_to_search = record.get("embedding")
    
    if not vector_to_search:
        logger.info("No embedding found. Generating on the fly...")
        try:
            embedder = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
            tx_data = record["input_data"]
            text_to_embed = f"Transaction amount: ${tx_data.get('Amount')}, Time: {tx_data.get('Time')}."
            vector_to_search = embedder.embed_query(text_to_embed)
            
            # Save it back to the DB
            update_transaction_embedding(transaction_id, vector_to_search)
        except Exception as e:
            return f"Error generating JIT embedding: {e}"

    # 3. Clean Vector Search using our new DB layer
    similar_records = search_similar_transactions(vector_to_search, exclude_id=transaction_id, limit=3)

    if not similar_records:
        return "No historical transactions with embeddings found to compare against."

    # 4. Format the context for the LLM
    report = "Historical Similar Transactions Found:\n"
    fraud_count = 0
    for row in similar_records:
        status = "FRAUD" if row["is_fraud"] else "LEGITIMATE"
        if row["is_fraud"]: fraud_count += 1
        report += f"- ID: {row['transaction_id'][:8]}... | Status: {status} | Amount: ${row['amount']:.2f} | Cosine Distance: {row['distance']:.4f}\n"
    
    report += f"\nConclusion: {fraud_count} out of the 3 most mathematically similar past transactions were flagged as {status}."
    return report