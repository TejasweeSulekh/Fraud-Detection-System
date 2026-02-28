import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

# Import your newly refactored tools
from src.agent.tools import analyze_shap_values, search_historical_fraud

logger = logging.getLogger("AgentCore")

class InvestigationReport(BaseModel):
    transaction_id: str = Field(description="The ID of the transaction being investigated.")
    is_fraud: bool = Field(description="True if the model flagged it as fraud, False otherwise.")
    risk_score: Optional[float] = Field(description="The numeric risk score/probability from the model, if available.")
    key_drivers: List[str] = Field(description="List of the top 3-5 feature names that drove the decision (e.g., ['V20', 'V16']).")
    historical_context: str = Field(description="A brief summary of whether similar historical transactions were found and their status.")
    executive_summary: str = Field(description="A professional, 2-3 sentence final verdict explaining the flag.")
    data_complete: bool = Field(description="False if any tools failed, True if all tools succeeded.")

def run_investigation(transaction_id: str) -> dict:
    """Runs the agentic workflow and returns a structured dictionary."""
    logger.info(f"🚀 Starting Investigation for {transaction_id}...")
    
    try:
        # 1. Setup Agent
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        tools = [analyze_shap_values, search_historical_fraud]
        agent_executor = create_react_agent(llm, tools)
        
        # 2. Advanced Prompting (Handling the PCA Interpretability)
        prompt = f"""
        You are an expert financial risk analyst. Investigate transaction {transaction_id}. 
        
        INSTRUCTIONS:
        1. Use the SHAP tool to find out why the model flagged it.
        2. Use the historical search tool to see if this pattern has happened before.
        3. DATA INTERPRETATION RULE: The features V1 through V28 are PCA-transformed, anonymized vectors representing hidden user behaviors. 
           Do NOT guess what they mean (e.g., do not say V16 is 'location'). Instead, refer to them professionally as "anomalous behavioral vectors" or "hidden variance metrics." 
           You CAN interpret the "Amount" and "Time" features literally.
        4. Write a short, highly professional 3-sentence summary combining both insights.
        """
        
        # 3. Execute
        for step_event in agent_executor.stream({"messages": [("user", prompt)]}):
            pass 
            
        final_state = list(step_event.values())[0]
        raw_final_message = final_state["messages"][-1].content
        if isinstance(raw_final_message, list):
            raw_final_message = raw_final_message[0].get("text", raw_final_message)

        # 4. Structure the Output
        logger.info("📝 Structuring the agent's report...")
        formatter_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        structured_llm = formatter_llm.with_structured_output(InvestigationReport)
        
        formatting_prompt = f"""
        Extract info from this report and format it strictly.
        Target Transaction ID: {transaction_id}
        Raw Report: {raw_final_message}
        """
        
        final_structured_report = structured_llm.invoke(formatting_prompt)
        return json.loads(final_structured_report.model_dump_json())
        
    except Exception as e:
        logger.warning(f"⚠️ Agent/Quota Failed. Returning Simulation Data. Error: {e}")
        
        return {
            "transaction_id": transaction_id,
            "is_fraud": True,
            "risk_score": 0.99,
            "key_drivers": ["V16 (Simulated)", "Amount (Simulated)"],
            "historical_context": "Simulated Data: The API quota is exhausted.",
            "executive_summary": "SIMULATED REPORT: The backend is connected properly. Awaiting API quota reset for live agent analysis.",
            "data_complete": False
        }