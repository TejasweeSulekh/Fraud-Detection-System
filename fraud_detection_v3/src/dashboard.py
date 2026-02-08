import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import os
import time
from sqlalchemy import create_engine

# --- CONFIGURATION ---
# The environment variable from docker-compose will override 'localhost'
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fraud_user:fraud_pass@localhost:5432/fraud_db")
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Fraud Detection Monitor",
    page_icon="🛡️",
    layout="wide"
)

# --- HELPER FUNCTIONS ---
def get_db_connection():
    return create_engine(DATABASE_URL)

def load_data():
    """Fetch the latest 100 transactions from Postgres"""
    engine = get_db_connection()
    # We query the 'predictions' table created by your new database script
    query = "SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 100"
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return pd.DataFrame()

def get_explanation(transaction_data):
    """Call the API to get SHAP values"""
    try:
        # Ensure data is a dict before sending
        if isinstance(transaction_data, str):
            transaction_data = json.loads(transaction_data)
            
        # The API expects the transaction structure, so we send the dict
        resp = requests.post(f"{API_URL}/explain", json=transaction_data)
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYOUT ---
st.title("🛡️ Real-Time Fraud Detection System")

# 1. Metrics Row
col1, col2, col3, col4 = st.columns(4)
df = load_data()

if not df.empty:
    total_tx = len(df)
    fraud_tx = df[df['is_fraud'] == True].shape[0]
    fraud_rate = (fraud_tx / total_tx) * 100 if total_tx > 0 else 0
    avg_latency = df['execution_time_ms'].mean()

    col1.metric("Total Transactions", total_tx)
    col2.metric("Fraud Detected", fraud_tx, delta_color="inverse")
    col3.metric("Fraud Rate", f"{fraud_rate:.2f}%")
    col4.metric("Avg Latency", f"{avg_latency:.1f}ms")

    # 2. Main Data Table
    st.subheader("🛑 Live Transaction Feed")
    
    def highlight_fraud(row):
        return ['background-color: #ffcccc' if row.is_fraud else '' for _ in row]

    # Show simplified table
    display_df = df[['transaction_id', 'timestamp', 'amount', 'is_fraud', 'fraud_probability']]
    st.dataframe(
        display_df.style.apply(highlight_fraud, axis=1), 
        use_container_width=True
    )

    # 3. Investigation & Explainability
    st.subheader("🔍 Investigator Mode")
    
    tx_ids = df['transaction_id'].tolist()
    selected_tx_id = st.selectbox("Select Transaction ID to Investigate:", tx_ids)

    if selected_tx_id:
        # Get the specific row
        row = df[df['transaction_id'] == selected_tx_id].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.info(f"**Status:** {'🚨 FRAUD' if row['is_fraud'] else '✅ LEGIT'}")
            st.write(f"**Amount:** ${row['amount']:.2f}")
            st.write(f"**Risk Score:** {row['fraud_probability']:.4f}")
            
            if st.button("Explain Decision"):
                with st.spinner("Asking AI Model..."):
                    input_data_raw = row['input_data']
                    
                    if input_data_raw:
                        explanation = get_explanation(input_data_raw)
                        
                        if "top_contributing_features" in explanation:
                            st.success("Explanation Generated!")
                            feats = explanation['top_contributing_features']
                            feat_df = pd.DataFrame(list(feats.items()), columns=['Feature', 'Impact'])
                            
                            fig = px.bar(
                                feat_df, 
                                x='Impact', 
                                y='Feature', 
                                orientation='h',
                                title="Why was this flagged? (SHAP Values)",
                                color='Impact',
                                color_continuous_scale='RdBu_r'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.error(f"Failed to explain: {explanation}")
                    else:
                        st.warning("No input data stored for this transaction.")

        with c2:
            st.write("### Raw Transaction Data")
            # Safe parse JSON string for display
            try:
                json_data = json.loads(row['input_data']) if isinstance(row['input_data'], str) else row['input_data']
                st.json(json_data)
            except:
                st.text(row['input_data'])

else:
    st.info("Waiting for transactions... (Check if Producer is running)")
    if st.button("Refresh"):
        st.rerun()

# Auto-refresh logic (every 2 seconds)
time.sleep(2)
st.rerun()