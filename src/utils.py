# src/utils.py
import os
import requests
import zipfile
import logging
from urllib.parse import urlencode
import streamlit as st
import gdown

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_and_extract_data(file_id, data_dir="data", zip_filename="creditcardfraud.zip"):
    """
    Downloads a zip file from Google Drive using gdown and extracts it.
    """
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    zip_path = os.path.join(data_dir, zip_filename)
    csv_path = os.path.join(data_dir, "creditcard.csv")

    # Check if extracted CSV already exists
    if os.path.exists(csv_path):
        logger.info(f"Data already exists at {csv_path}. Skipping download.")
        return csv_path

    # Check if Zip exists, if not, download
    if not os.path.exists(zip_path):
        logger.info(f"Downloading dataset (ID: {file_id}) via gdown...")
        try:
            # THE FIX: Use gdown to handle the Google Drive virus-scan warning
            gdown.download(id=file_id, output=zip_path, quiet=False)
            logger.info("Download complete.")
        except Exception as e:
            logger.error(f"Failed to download data: {e}")
            return None

    # Extract
    if os.path.exists(zip_path):
        logger.info("Extracting data...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(data_dir)
            logger.info("Extraction complete.")
            
            # Cleanup zip to save space
            os.remove(zip_path)
            return csv_path
        except zipfile.BadZipFile:
            logger.error("Downloaded file is not a valid zip file. Google Drive might have blocked the download.")
            return None
    
    return None

# def download_file_from_google_drive(id, destination):
#     URL = "https://docs.google.com/uc/export"
    
#     session = requests.Session()
#     response = session.get(URL, params={'id': id}, stream=True)
    
#     token = get_confirm_token(response)

#     if token:
#         params = {'id': id, 'confirm': token}
#         response = session.get(URL, params=params, stream=True)

#     save_response_content(response, destination)   

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None

# def save_response_content(response, destination):
#     CHUNK_SIZE = 32768
    
#     with open(destination, "wb") as f:
#         for chunk in response.iter_content(CHUNK_SIZE):
#             if chunk: # filter out keep-alive new chunks
#                 f.write(chunk)

# def download_and_extract_data(file_id, data_dir="data", zip_filename="creditcardfraud.zip"):
#     """
#     Downloads a zip file from Google Drive and extracts it.
    
#     Args:
#         file_id (str): The Google Drive File ID (from the shareable link).
#         data_dir (str): The directory where data should be stored.
#         zip_filename (str): The name of the downloaded zip file.
#     """
#     if not os.path.exists(data_dir):
#         os.makedirs(data_dir)
        
#     zip_path = os.path.join(data_dir, zip_filename)
#     csv_path = os.path.join(data_dir, "creditcard.csv")

#     # Check if extracted CSV already exists
#     if os.path.exists(csv_path):
#         logger.info(f"Data already exists at {csv_path}. Skipping download.")
#         return csv_path

#     # Check if Zip exists, if not, download
#     if not os.path.exists(zip_path):
#         logger.info(f"Downloading dataset (ID: {file_id})...")
#         try:
#             download_file_from_google_drive(file_id, zip_path)
#             logger.info("Download complete.")
#         except Exception as e:
#             logger.error(f"Failed to download data: {e}")
#             return None

#     # Extract
#     if os.path.exists(zip_path):
#         logger.info("Extracting data...")
#         try:
#             with zipfile.ZipFile(zip_path, 'r') as zip_ref:
#                 zip_ref.extractall(data_dir)
#             logger.info("Extraction complete.")
            
#             # Cleanup zip to save space
#             os.remove(zip_path)
#             return csv_path
#         except zipfile.BadZipFile:
#             logger.error("Downloaded file is not a valid zip file.")
#             return None
    
#     return None

API_URL = os.getenv("API_URL", "http://inference-service:8000")

def fetch_agent_investigation(transaction_id: str):
    """Fetches the structured report from the Agentic API."""
    try:
        # Agents take time to think. A 60-second timeout prevents Streamlit from giving up too early.
        response = requests.get(f"{API_URL}/investigate/{transaction_id}", timeout=60)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        st.error("🚨 Connection Refused: Is the FastAPI server running and port-forwarded?")
        return None
    except requests.exceptions.Timeout:
        st.error("⏳ Timeout: The Agent took too long to respond.")
        return None
    except Exception as e:
        st.error(f"⚠️ Unexpected Error: {str(e)}")
        return None