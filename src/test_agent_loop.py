import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

load_dotenv()

# --- 1. The Tool ---
@tool
def get_user_risk_score(user_id: str) -> int:
    """
    Fetches the historical risk score for a given user_id. 
    A score above 80 is considered high risk.
    """
    print(f"\n[SYSTEM LOG] Executing database query for: {user_id}...")
    return 85 

def test_agent():
    print("Initializing LLM...")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    tools = [get_user_risk_score]

    # --- 2. The Loop (LangGraph) ---
    # LangGraph handles the system prompts and the tool execution loop natively
    agent_executor = create_react_agent(llm, tools)

    print("\nStarting the Agent loop...\n")
    
    # We invoke the Executor with a dictionary containing a list of messages
    result = agent_executor.invoke({
        "messages": [("user", "What is the risk score for user U-9942? Are they high risk?")]
    })
    
    print("\n--- FINAL OUTPUT ---")
    # The final plain-text answer from the LLM is stored in the content of the very last message
    print(result["messages"][-1].content)

if __name__ == "__main__":
    test_agent()