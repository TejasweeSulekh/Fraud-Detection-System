import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

def test_connection():
    print("Initializing LLM...")
    
    # Using Gemini's fast, free-tier model
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    print("Sending ping to Gemini...")
    
    response = llm.invoke("If a transaction is $5000 and the user normally spends $50, is that anomalous? Answer in one sentence.")
    
    print("\n--- LLM RESPONSE ---")
    print(response.content)

if __name__ == "__main__":
    test_connection()