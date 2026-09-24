import streamlit as st
import pandas as pd
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Page Config
st.set_page_config(page_title="AI Procurement Copilot", layout="wide")
st.title("📦 RFx Copilot & Vendor Comparison Hub")

# Initialize Vertex AI Client
@st.cache_resource
def get_genai_client():
    # Pass GCP Service Account credentials from Streamlit Secrets
    credentials_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
    return genai.Client(
        vertexai=True,
        project=credentials_info["project_id"],
        location="us-central1",
        credentials=credentials_info
    )

client = get_genai_client()

# --- TAB NAVIGATION ---
tab1, tab2, tab3 = st.tabs(["1️⃣ RFx Creator", "2️⃣ Ingestion & Matrix", "3️⃣ Interrogate & Award"])

# ---------------------------------------------------------
# TAB 1: RFx Copilot Creation
# ---------------------------------------------------------
with tab1:
    st.subheader("RFx #2026-PKG-001: Corrugated Packaging Sourcing")
    st.info("AI Co-pilot generated 30 target line items and vendor questionnaires.")
    
    # Pre-populated target RFx ground truth
    rfq_items = [
        {"item_id": f"ITEM-{i+1:03d}", "description": f"Corrugated Box Type-{i+1}", "target_qty": (i+1)*1000, "target_uom": "pcs"}
        for i in range(30)
    ]
    st.dataframe(pd.DataFrame(rfq_items), use_container_width=True, height=300)

# ---------------------------------------------------------
# TAB 2: Vendor Document Ingestion & Extraction Grid
# ---------------------------------------------------------
with tab2:
    st.subheader("Vendor Responses & Extraction Grid")
    uploaded_files = st.file_uploader("Upload Vendor Quotes (PDF, PNG, TXT)", accept_multiple_files=True)
    
    if st.button("Run AI Extraction & Normalization"):
        st.warning("Extracting vendor quotes using Gemini 2.5 Flash...")
        # Call extraction pipeline here and format side-by-side DataFrame
        # Highlight partial quotes (e.g. 27/30), currency mismatches, UOM conversions
        
# ---------------------------------------------------------
# TAB 3: Conversational Interrogation & Analysis
# ---------------------------------------------------------
with tab3:
    st.subheader("Interrogate Matrix & Scenario Analysis")
    
    user_query = st.text_input(
        "Ask a question across all vendor quotes:",
        placeholder="e.g., What if we split the award, picking the cheapest vendor per line item who passed quality?"
    )
    
    if user_query:
        with st.spinner("Analyzing across 5 vendor quotes..."):
            prompt = f"""
            You are a chief procurement analyst. Answer the user question based on the extracted quote matrix.
            User Query: {user_query}
            Provide text reasoning, a summary table, and a clear award recommendation.
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            st.markdown(response.text)
