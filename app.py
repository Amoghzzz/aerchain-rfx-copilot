import streamlit as st
import pandas as pd
import json
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain AI RFx Copilot",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Aerchain AI RFx Copilot & Vendor Comparison Matrix")
st.caption("Automated RFx creation, unstructured vendor document extraction, and conversational interrogation.")

# -----------------------------------------------------------------------------
# 2. VERTEX AI CLIENT INITIALIZATION
# -----------------------------------------------------------------------------
@st.cache_resource
def get_genai_client():
    # Retrieve service account credentials from Streamlit secrets
    creds_dict = dict(st.secrets["GCP_SERVICE_ACCOUNT"])
    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    
    return genai.Client(
        vertexai=True,
        project=creds_dict["project_id"],
        location="us-central1",
        credentials=credentials
    )

try:
    client = get_genai_client()
except Exception as e:
    st.error(f"Failed to authenticate with GCP Vertex AI: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. MOCK DATA INITIALIZATION (30 Line Items & 5 Vendors)
# -----------------------------------------------------------------------------
@st.cache_data
def get_rfx_baseline():
    categories = ["3-Ply Standard Box", "5-Ply Heavy Duty Box", "Custom Printed Mailer", "Corrugated Partition Tray"]
    items = []
    for i in range(1, 31):
        cat = categories[(i - 1) % len(categories)]
        items.append({
            "Line #": f"LINE-{i:03d}",
            "Item Description": f"{cat} - Spec Variant {i}",
            "Target Qty": (i * 500) + 1000,
            "UOM": "pcs",
            "Target Spec": "180 GSM Kraft Paper" if i % 2 == 0 else "150 GSM Kraft Paper"
        })
    return pd.DataFrame(items)

@st.cache_data
def get_vendor_mock_matrix():
    base_df = get_rfx_baseline().copy()
    
    # Simulating vendor extractions with edge cases
    # Vendor 1: Apex Packaging (Standard baseline)
    base_df["Apex (INR/pc)"] = [round(20 + (i * 0.8), 2) for i in range(30)]
    
    # Vendor 2: PackTech (Unit mismatch: quoted per 100 pcs originally, normalized here)
    base_df["PackTech (INR/pc)*"] = [round(19 + (i * 0.85), 2) for i in range(30)]
    
    # Vendor 3: BoxCraft (Partial quote: only quoted 27 of 30 items)
    base_df["BoxCraft (INR/pc)"] = [round(18 + (i * 0.75), 2) if i < 27 else None for i in range(30)]
    
    # Vendor 4: CorruSeal (Currency mismatch: converted from USD to INR at 83.5)
    base_df["CorruSeal (USD->INR)"] = [round((0.23 + (i * 0.01)) * 83.5, 2) for i in range(30)]
    
    # Vendor 5: National Paper Mills (Competitive on high volume)
    base_df["National Paper (INR/pc)"] = [round(22 + (i * 0.7), 2) for i in range(30)]
    
    return base_df

# -----------------------------------------------------------------------------
# 4. TABBED INTERFACE
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["1️⃣ RFx Setup & Ground Truth", "2️⃣ Ingestion & Side-by-Side Matrix", "3️⃣ Interrogate & Split-Award Analyst"])

# -----------------------------------------------------------------------------
# TAB 1: RFX SETUP
# -----------------------------------------------------------------------------
with tab1:
    st.header("RFx #RFQ-2026-PKG-001: Corrugated Packaging Sourcing")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Target 30 Line Items Scope")
        st.dataframe(get_rfx_baseline(), use_container_width=True, height=400)
    
    with col2:
        st.subheader("Quality Questionnaire & Terms")
        st.markdown("""
        * **Payment Terms:** Net 60 Days
        * **Delivery Location:** Central Warehouse (Bhiwandi / Hosur)
        * **Quality Assessment Criteria:**
          1. ISO 9001 Certified? (Mandatory)
          2. Bursting Strength Test Certificate attached?
          3. Maximum Defect Rate Tolerance: < 0.5%
        """)
        st.info("Vendors were invited to submit quotes via PDF, Email, Excel, or scanned rate cards.")

# -----------------------------------------------------------------------------
# TAB 2: INGESTION & EXTRACTION MATRIX
# -----------------------------------------------------------------------------
with tab2:
    st.header("Multi-Vendor Extraction Grid")
    
    st.markdown("### Upload Incoming Vendor Quotes (Simulated OCR & Parser)")
    uploaded_files = st.file_uploader(
        "Drop vendor PDFs, images (photos of rate cards), or text emails here:",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "txt"]
    )
    
    if uploaded_files:
        st.success(f"Received {len(uploaded_files)} document(s). Processing through Gemini 2.5 Flash multimodal pipeline...")
        # In a real run, client.models.generate_content would parse these directly.
    
    st.divider()
    st.subheader("Normalized Side-by-Side Comparison")
    
    # Edge case callout badges
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Vendors", "5")
    c2.warning("⚠️ BoxCraft: Partial Quote (27/30 items)")
    c3.info("💱 CorruSeal: Quoted in USD ($0.23/pc) → Auto-converted @ 83.5 INR")
    c4.error("📏 PackTech: Unit Mismatch ('per 100 pcs') → Auto-normalized")
    
    matrix_df = get_vendor_mock_matrix()
    st.dataframe(
        matrix_df.style.highlight_null(color="rgba(255, 99, 71, 0.3)"),
        use_container_width=True,
        height=450
    )

# -----------------------------------------------------------------------------
# TAB 3: CONVERSATIONAL INTERROGATION (GEMINI POWERED)
# -----------------------------------------------------------------------------
with tab3:
    st.header("Interrogate the Matrix in Plain Language")
    st.markdown("Ask complex analytical questions, run split-award scenarios, or verify hidden footnotes across all vendor responses.")
    
    # Sample Query Quick Buttons
    st.markdown("**Suggested Quick Prompts:**")
    q_col1, q_col2, q_col3 = st.columns(3)
    
    prompt_choice = None
    if q_col1.button("💡 Split-award: Cheapest vendor per item"):
        prompt_choice = "Show me a split-award decision picking the absolute cheapest vendor for each line item. Calculate total cost and savings compared to single vendor."
    if q_col2.button("⚠️ Identify risk & partial quotes"):
        prompt_choice = "Which vendors failed to quote all 30 line items, and what risk does that pose to our procurement timeline?"
    if q_col3.button("📊 Best overall single-vendor award"):
        prompt_choice = "If we must award 100% of the volume to a single vendor for supply chain simplicity, who should we choose and why?"

    user_query = st.text_input("Or enter your own question:", value=prompt_choice if prompt_choice else "")
    
    if user_query:
        with st.spinner("Analyzing all vendor quotes with Gemini 2.5 Flash..."):
            # Prepare extraction summary to send as context to Gemini
            matrix_json = get_vendor_mock_matrix().to_json(orient="records")
            
            system_instruction = """
            You are an expert Chief Procurement Officer (CPO) AI assistant. 
            You are analyzing an RFx matrix of 30 line items across 5 vendors.
            Vendor Edge Cases:
            - BoxCraft quoted only 27 of 30 items.
            - CorruSeal quoted in USD (converted to INR at 83.5).
            - PackTech quoted per 100 pcs (normalized to per piece).
            
            Answer the user query accurately based on the data provided. 
            Structure your response with clear markdown headings, bullet points, and a concluding recommendation.
            """
            
            prompt = f"Data Matrix (JSON):\n{matrix_json}\n\nUser Question: {user_query}"
            
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                
                st.markdown("### AI Analyst Insights")
                st.write(response.text)
                
                # Visual Chart Example
                st.markdown("### Cost Breakdown Visualizer")
                summary_data = pd.DataFrame({
                    "Vendor": ["Apex", "PackTech", "BoxCraft (Partial)", "CorruSeal", "National Paper"],
                    "Estimated Total Cost (INR)": [1050000, 1020000, 890000, 1120000, 980000]
                })
                fig = px.bar(
                    summary_data, 
                    x="Vendor", 
                    y="Estimated Total Cost (INR)", 
                    color="Vendor",
                    title="Total Commercial Spend Comparison"
                )
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Error querying Gemini API: {e}")
