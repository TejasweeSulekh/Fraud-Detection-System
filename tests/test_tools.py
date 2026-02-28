import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

load_dotenv()

# --- 1. Define the "Hands" (The Tool) ---
# The @tool decorator tells LangChain this is a function the LLM can use.
# The docstring is CRITICAL: it is how the LLM knows what the tool does.
@tool
def get_user_risk_score(user_id: str) -> int:
    """
    Fetches the historical risk score for a given user_id. 
    A score above 80 is considered high risk.
    """
    print(f"\n[SYSTEM LOG] Actually running the Python function for: {user_id}...")
    # In the future, this will be: pd.read_sql("SELECT risk FROM...", engine)
    return 85 

def test_tool_calling():
    print("Initializing LLM...")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # --- 2. Bind the Tools ---
    # We create a new version of the LLM that is aware of the tools
    tools = [get_user_risk_score]
    llm_with_tools = llm.bind_tools(tools)
    
    print("Asking the LLM a question that requires the tool...")
    
    # --- 3. The Invocation ---
    # We ask a specific question. The LLM will read the tools, realize it 
    # doesn't know the answer inherently, and ask to use `get_user_risk_score`.
    response = llm_with_tools.invoke("What is the risk score for user U-9942? Is it high risk?")
    
    print("\n--- LLM RESPONSE OBJECT ---")
    print(f"Standard Text Output: '{response.content}'")
    print(f"Tool Calls Requested: {response.tool_calls}")

if __name__ == "__main__":
    test_tool_calling()