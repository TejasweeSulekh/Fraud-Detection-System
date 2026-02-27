import os
import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

load_dotenv() # Make sure you have OPENAI_API_KEY in your local .env file

# We use a relatively capable model here because Tool Calling requires good reasoning
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

@tool
def get_shap_values(transaction_id: str) -> dict:
    """
    Fetches the SHAP value explanations for a flagged transaction.
    Use this tool FIRST when investigating why a transaction was flagged as fraud.
    """
    # For this local test, we will mock the response of your FastAPI /explain endpoint
    # In production, this would be: requests.post(f"{API_URL}/explain", json={"transaction_id": transaction_id, ...})
    
    print(f"\n[Tool Execution] Fetching SHAP values for {transaction_id}...")
    
    # Mock data mimicking your explainer output
    return {
        "transaction_id": transaction_id,
        "top_contributing_features": {
            "V14": -4.23,
            "V4": 3.12,
            "Amount": 2500.00
        }
    }

@tool
def query_user_history(transaction_id: str) -> str:
    """
    Searches the vector database for the user's past transaction behavior.
    Use this tool to see if the current transaction amount or location matches their historical baseline.
    """
    print(f"\n[Tool Execution] Querying vector DB for history related to {transaction_id}...")
    # Mocking pgvector retrieval
    return "User typically makes transactions under $50. No history of large purchases."

# We bundle the tools into a list so the agent knows what it has access to
tools = [get_shap_values, query_user_history]

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an elite Fraud Investigation AI. 
    A Random Forest model has flagged a transaction for potential fraud. 
    Your job is to investigate this transaction using the provided tools and write a final summary report.
    
    Follow these steps strictly:
    1. Fetch the SHAP values to see WHY the model flagged it.
    2. Check the user's historical transaction behavior.
    3. Synthesize this information into a clear verdict (Fraud or False Positive) with a short explanation."""),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"), # This is where the agent stores its intermediate thoughts and tool results
])

# Bind tools to the LLM
agent = create_tool_calling_agent(llm, tools, prompt)

# The executor runs the reasoning loop
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

if __name__ == "__main__":
    test_transaction = "TXN-9982-XYZ"
    print(f"--- Starting Investigation for {test_transaction} ---")
    
    # Kick off the agent
    result = agent_executor.invoke({"input": f"Investigate transaction {test_transaction}."})
    
    print("\n--- FINAL AGENT REPORT ---")
    print(result["output"])