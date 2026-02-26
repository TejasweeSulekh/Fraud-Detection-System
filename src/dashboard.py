import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import os
import time
import logging
from sqlalchemy import create_engine

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("Dashboard")

# --- CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://fraud_user:fraud_pass@postgres:5432/fraud_db")
# Docker DNS: use 'inference-service', not localhost
API_URL = os.getenv("API_URL", "http://inference-service:8000")

st.set_page_config(
    page_title="Fraud Detection Monitor",
    layout="wide"
)

# --- HELPER FUNCTIONS ---
def get_db_connection():
    return create_engine(DATABASE_URL)

def load_data():
    """Fetch the latest 100 transactions from Postgres"""
    try:
        engine = get_db_connection()
        query = "SELECT * FROM predictions ORDER BY timestamp DESC LIMIT 100"
        return pd.read_sql(query, engine)
    except Exception as e:
        logger.error(f"Database error: {e}")
        st.error("Database connection failed.")
        return pd.DataFrame()

def get_explanation(transaction_data):
    """Call the API to get SHAP values"""
    try:
        if isinstance(transaction_data, str):
            transaction_data = json.loads(transaction_data)
            
        # logger.info("Requesting explanation from API...")
        resp = requests.post(f"{API_URL}/explain", json=transaction_data, timeout=3)
        
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}

def render_explanation(row):
    """Renders the SHAP plot for a given row of data"""
    with st.spinner("Analyzing Model Decision..."):
        input_data_raw = row['input_data']
        
        if input_data_raw:
            explanation = get_explanation(input_data_raw)
            
            if "top_contributing_features" in explanation:
                feats = explanation['top_contributing_features']
                feat_df = pd.DataFrame(list(feats.items()), columns=['Feature', 'Impact'])
                
                fig = px.bar(
                    feat_df, 
                    x='Impact', 
                    y='Feature', 
                    orientation='h',
                    title=f"Why was {row['transaction_id'][:8]}... flagged?",
                    color='Impact',
                    color_continuous_scale='RdBu_r'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"Failed to explain: {explanation}")
        else:
            st.warning("No input data stored for this transaction.")

# --- UI LAYOUT ---
st.title("Real-Time Fraud Detection System")

# SIDEBAR CONTROLS
st.sidebar.header("Controls")
# Using session state to ensure the checkbox doesn't flicker
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True

auto_refresh = st.sidebar.checkbox("Enable Live Updates", value=st.session_state.auto_refresh)

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
    st.subheader("Live Transaction Feed")
    
    def highlight_fraud(row):
        return ['background-color: #ffcccc' if row.is_fraud else '' for _ in row]

    display_df = df[['transaction_id', 'timestamp', 'amount', 'is_fraud', 'fraud_probability']]
    st.dataframe(
        display_df.style.apply(highlight_fraud, axis=1), 
        use_container_width=True,
        height=300
    )

    # 3. Dynamic Explanation Section
    st.markdown("---")
    st.subheader("Model Decision Explainer")

    c1, c2 = st.columns([1, 2])

    with c1:
        # LOGIC SPLIT: LIVE vs PAUSED
        target_row = None
        
        if auto_refresh:
            st.info("🔴 LIVE MODE: Updates automatically show the latest transaction.")
            # Use a toggle instead of a button
            show_live_shap = st.toggle("Explain Stream (Latest Transaction)", value=False)
            
            if show_live_shap:
                # In live mode, we always grab the top row (index 0)
                target_row = df.iloc[0]
                
        else:
            st.info("⏸️ INVESTIGATION MODE: Feed paused. Select specific ID.")
            tx_ids = df['transaction_id'].tolist()
            selected_tx_id = st.selectbox("Select Transaction ID:", tx_ids)
            
            # In paused mode, we find the specific row selected
            if selected_tx_id:
                target_row = df[df['transaction_id'] == selected_tx_id].iloc[0]

        # Display details if a row is targeted
        if target_row is not None:
            st.write(f"**Transaction:** `{target_row['transaction_id']}`")
            st.write(f"**Amount:** `${target_row['amount']:.2f}`")
            st.write(f"**Risk Score:** `{target_row['fraud_probability']:.4f}`")
            
            status_color = "red" if target_row['is_fraud'] else "green"
            st.markdown(f"**Status:** :{status_color}[{'FRAUD' if target_row['is_fraud'] else 'LEGIT'}]")

    with c2:
        if target_row is not None:
            # If we are in Live Mode with toggle ON, or Paused Mode with a selection
            if auto_refresh and show_live_shap:
                render_explanation(target_row)
            elif not auto_refresh:
                # In paused mode, always render (or you can add a toggle here too if you want)
                render_explanation(target_row)
        else:
            st.info("Select a transaction or enable 'Explain Stream' to see details.")

else:
    st.info("Waiting for transactions... (Check if Producer is running)")

# --- AUTO REFRESH LOGIC ---
if auto_refresh:
    time.sleep(2)
    st.rerun()