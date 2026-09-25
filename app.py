import streamlit as st
import pandas as pd
import json
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & CUSTOM ENTERPRISE STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | AI RFx Intelligence Hub",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern enterprise UI
st.markdown("""
    <style>
    /* Global background and typography adjustments */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Card/Container Styling */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700;
        color: #38bdf8;
    }
    
    /* Custom Badges */
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        padding: 4px 8px;
        border-radius: 6px;
        border: 1px solid #f59e0b;
        font-size: 0.85rem;
    }
    .badge-info {
        background-color: rgba(56, 189, 248, 0.2);
        color: #38bdf8;
        padding: 4px 8px;
        border-radius: 6px;
        border: 1px solid #0284c7;
        font-size: 0.85rem;
    }
    .badge-error {
        background-color: rgba(239, 68, 68, 0.2);
        color: #f87171;
        padding: 4px 8px;
        border-radius: 6px;
        border: 1px solid #dc2626;
        font-size: 0.85rem;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1e293b;
        border-radius: 8px 8px 0px 0px;
        color: #94a3b8;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284c7 !important;
        color: #ffffff !important;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar Branding & System Metrics
with st.sidebar:
    st.image("https://img.icons8.com/isometric-folders/100/box.png", width=60)
    st.title("Aerchain Intelligence")
    st.caption("Active Workspace: **Packaging Sourcing 2026**")
    st.divider()
    
    st.markdown("### System Health")
    st.success("🟢 Vertex AI (Gemini 2.5 Flash): Connected")
    st.info("⚡ Normalization Engine: Ready")
    
    st.divider()
    st.markdown("### Audit & Trust Controls")
    st.checkbox("Enable Source Citation Hover", value=True)
    st.checkbox("Highlight High-Risk Footnotes", value=True)

# Header Section
st.title("📦 RFx Copilot & Autonomous Comparison Hub")
st.caption("Eliminating Quote Spreadsheets through Multimodal Extraction & Natural Language Interrogation.")

# -----------------------------------------------------------------------------
# 2. VERTEX AI CLIENT INITIALIZATION
# -----------------------------------------------------------------------------
@st.cache_resource
def get_genai_client():
    creds_dict = dict(st.secrets["GCP_SERVICE_ACCOUNT"])
    if "token_uri" not in creds_dict:
        creds_dict["token_uri"] = "https://oauth2.googleapis.com/token"

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )
    
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
# 3. MOCK DATA INITIALIZATION
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
    base_df["Apex (INR/pc)"] = [round(20 + (i * 0.8), 2) for i in range(30)]
    base_df["PackTech (INR/pc)"] = [round(19 + (i * 0.85), 2) for i in range(30)]
    base_df["BoxCraft (INR/pc)"] = [round(18 + (i * 0.75), 2) if i < 27 else None for i in range(30)]
    base_df["CorruSeal (USD->INR)"] = [round((0.23 + (i * 0.01)) * 83.5, 2) for i in range(30)]
    base_df["National Paper (INR/pc)"] = [round(22 + (i * 0.7), 2) for i in range(30)]
    return base_df

# -----------------------------------------------------------------------------
# 4. TABBED INTERFACE
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "1️⃣ RFx Setup & Scope Ground Truth", 
    "2️⃣ Ingestion & Interactive Matrix", 
    "3️⃣ Conversational Interrogation & Award"
])

# -----------------------------------------------------------------------------
# TAB 1: RFX SETUP
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("RFx Scope: Corrugated Packaging (30 Line Items)")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**Master Line Items Table**")
        st.dataframe(get_rfx_baseline(), use_container_width=True, height=400)
    
    with col2:
        st.markdown("**Qualitative Questionnaire & Terms**")
        st.info("""
        * **Payment Terms Target:** Net 60 Days
        * **Delivery Locations:** Central Warehouses (Bhiwandi / Hosur)
        * **Mandatory Criteria:** ISO 9001, Quality Defect Rate < 0.5%
        """)
        st.markdown("**Invited Vendors (5):**")
        st.write("1. Apex Packaging | 2. PackTech Solutions | 3. BoxCraft Ltd | 4. CorruSeal Global | 5. National Paper Mills")

# -----------------------------------------------------------------------------
# TAB 2: INGESTION & INTERACTIVE COMPARISON MATRIX
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Multi-Vendor Extraction Grid & Anomaly Monitor")
    
    # Upload Bar
    uploaded_files = st.file_uploader(
        "Upload incoming vendor files (PDFs, Images, Emails):",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "txt"]
    )
    if uploaded_files:
        st.success(f"Processing {len(uploaded_files)} file(s) via Gemini 2.5 Flash multimodal parser...")
    
    st.divider()
    
    # Visual Anomaly Badges
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Ingested Vendors", "5 / 5")
    b2.markdown("<div class='badge-warning'>⚠️ BoxCraft: Partial Quote (27/30 items)</div>", unsafe_allow_html=True)
    b3.markdown("<div class='badge-info'>💱 CorruSeal: USD Converted @ 83.5 INR</div>", unsafe_allow_html=True)
    b4.markdown("<div class='badge-error'>📏 PackTech: Unit Normalized ('per 100 pcs')</div>", unsafe_allow_html=True)
    
    st.write("")
    
    # Interactive Data Editor for Buyer Overrides
    st.markdown("**Side-by-Side Normalized Comparison (Double-click any cell to override):**")
    raw_matrix = get_vendor_mock_matrix()
    edited_matrix = st.data_editor(
        raw_matrix,
        use_container_width=True,
        height=400,
        num_rows="fixed"
    )
    
    # Source Document Audit Snippets
    with st.expander("📄 View Source Document Citations & OCR Snippets"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Source Document Snippet (BoxCraft Email Response):**")
            st.code("""
            From: sales@boxcraft.com
            Subject: Re: RFx Packaging Bid
            "Hi Team, attached pricing for items 1 through 27. 
            For items 28-30, rest same as last year rates."
            """, language="text")
        with col_b:
            st.markdown("**AI Extraction Log:**")
            st.json({
                "vendor": "BoxCraft",
                "extracted_lines": 27,
                "missing_lines": [28, 29, 30],
                "confidence_score": "0.94",
                "action": "Flagged as Partial Quote"
            })

# -----------------------------------------------------------------------------
# TAB 3: CONVERSATIONAL INTERROGATION (GEMINI POWERED)
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Interrogate the Comparison Matrix in Natural Language")
    
    # Quick Prompt Buttons
    st.markdown("**Suggested CPO Queries:**")
    q1, q2, q3 = st.columns(3)
    
    prompt_choice = None
    if q1.button("💡 Split-award: Lowest cost per line"):
        prompt_choice = "Show me a split-award decision picking the cheapest vendor for each line item. Calculate total cost and savings compared to single vendor."
    if q2.button("⚠️ Risk analysis on partial quotes"):
        prompt_choice = "Which vendors failed to quote all 30 line items, and what risk does that pose to our procurement timeline?"
    if q3.button("📊 Best single-vendor recommendation"):
        prompt_choice = "If we must award 100% of the volume to a single vendor for supply chain simplicity, who should we choose and why?"

    user_query = st.text_input("Ask a question across all vendor responses:", value=prompt_choice if prompt_choice else "")
    
    if user_query:
        with st.spinner("Analyzing matrix with Gemini 2.5 Flash..."):
            matrix_json = edited_matrix.to_json(orient="records")
            
            system_instruction = """
            You are an expert Chief Procurement Officer (CPO) AI assistant. 
            You are analyzing an RFx matrix of 30 line items across 5 vendors.
            Vendor Edge Cases:
            - BoxCraft quoted only 27 of 30 items.
            - CorruSeal quoted in USD (converted to INR at 83.5).
            - PackTech quoted per 100 pcs (normalized to per piece).
            
            Answer the query precisely with clear markdown headers, bullet points, and actionable savings metrics.
            """
            
            prompt = f"Data Matrix (JSON):\n{matrix_json}\n\nUser Query: {user_query}"
            
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                
                st.markdown("### AI Chief Procurement Officer Analysis")
                st.write(response.text)
                
                st.divider()
                st.markdown("### Spend Comparison Visualizer")
                
                # Dynamic spend chart
                summary_data = pd.DataFrame({
                    "Vendor": ["Apex", "PackTech", "BoxCraft (Partial)", "CorruSeal", "National Paper"],
                    "Total Quoted Spend (INR)": [1050000, 1020000, 890000, 1120000, 980000]
                })
                fig = px.bar(
                    summary_data, 
                    x="Vendor", 
                    y="Total Quoted Spend (INR)", 
                    color="Vendor",
                    template="plotly_dark",
                    title="Comparative Total Spend Across All Line Items"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Export Button
                csv = edited_matrix.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Decision Note & Extraction Matrix (CSV)",
                    data=csv,
                    file_name="RFx_Comparison_Decision_Note.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"Error querying Gemini API: {e}")
