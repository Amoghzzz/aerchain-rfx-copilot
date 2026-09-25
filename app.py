import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & CLEAN SAAS STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | RFx Smart Quote Assistant",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed" # Hide left sidebar completely
)

# Clean, High-Contrast Modern Theme CSS
st.markdown("""
    <style>
    /* Force main background */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Hide Sidebar Completely */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Top Header Summary Card */
    .top-header-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 24px;
        margin-bottom: 24px;
    }
    
    /* Fix Button Styling (Ensures black/dark text on light buttons) */
    .stButton>button {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 10px 16px !important;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #7dd3fc !important;
        color: #0f172a !important;
    }

    /* Tab Header Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #0f172a;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: #1e293b !important;
        border-radius: 8px;
        color: #94a3b8 !important; /* Visible light gray text for inactive tabs */
        padding: 10px 24px;
        font-weight: 600;
        border: 1px solid #334155;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284c7 !important; /* Active tab blue */
        color: #ffffff !important;
        font-weight: 700;
        border: 1px solid #38bdf8;
    }
    
    /* Alert Cards */
    .card-warn {
        background-color: #451a03;
        color: #fef08a;
        border: 1px solid #854d0e;
        padding: 12px 16px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
    }
    .card-info {
        background-color: #0c4a6e;
        color: #bae6fd;
        border: 1px solid #0284c7;
        padding: 12px 16px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
    }
    .card-danger {
        background-color: #450a0a;
        color: #fecdd3;
        border: 1px solid #9f1239;
        padding: 12px 16px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. TOP EXECUTIVE HEADER (REPLACES SIDEBAR)
# -----------------------------------------------------------------------------
st.title("📦 Aerchain RFx Smart Quote Assistant")
st.caption("Automated vendor quote standardisation, anomaly detection, and decision interrogation.")

# Full-width Context Bar
st.markdown("""
<div class="top-header-card">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <span style="color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Sourcing Event</span><br>
            <strong style="font-size: 1.1rem; color: #f8fafc;">RFQ-2026-PKG: Corrugated Packaging</strong>
        </div>
        <div>
            <span style="color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Scope</span><br>
            <strong style="font-size: 1.1rem; color: #38bdf8;">30 Line Items</strong>
        </div>
        <div>
            <span style="color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">Bids Received</span><br>
            <strong style="font-size: 1.1rem; color: #f8fafc;">5 Vendors Submitted</strong>
        </div>
        <div>
            <span style="color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; font-weight: 600;">AI Extraction Engine</span><br>
            <strong style="font-size: 1.1rem; color: #4ade80;">🟢 Gemini 2.5 Flash Active</strong>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. VERTEX AI CLIENT INITIALIZATION
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
    st.error(f"Failed to connect to AI engine: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 4. DATA ENGINE
# -----------------------------------------------------------------------------
@st.cache_data
def get_rfx_baseline():
    categories = ["3-Ply Standard Box", "5-Ply Heavy Duty Box", "Custom Printed Mailer", "Corrugated Partition Tray"]
    items = []
    for i in range(1, 31):
        cat = categories[(i - 1) % len(categories)]
        items.append({
            "Line #": f"LINE-{i:03d}",
            "Item Description": f"{cat} - Variant {i}",
            "Quantity": (i * 500) + 1000,
            "Unit": "pcs",
            "Specification": "180 GSM Kraft" if i % 2 == 0 else "150 GSM Kraft"
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
# 5. TABBED INTERFACE (HIGH CONTRAST & FULL WIDTH)
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "1️⃣ RFx Setup & Line Items", 
    "2️⃣ Vendor Comparison Table", 
    "3️⃣ AI Analysis & Award Decision"
])

# -----------------------------------------------------------------------------
# TAB 1: RFX SETUP
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("RFx Baseline Requirements")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**Master Requirement List (30 Line Items)**")
        st.dataframe(get_rfx_baseline(), use_container_width=True, height=420, hide_index=True)
    
    with col2:
        st.markdown("**Commercial Terms & Quality Standards**")
        st.info("""
        * **Target Payment Terms:** Net 60 Days
        * **Delivery Location:** Central Warehouses (Bhiwandi / Hosur)
        * **Quality Certification:** ISO 9001 Mandatory
        * **Defect Rate Limit:** Maximum 0.5%
        """)
        
        st.markdown("**Invited Suppliers (5):**")
        st.write("1. Apex Packaging | 2. PackTech Solutions | 3. BoxCraft Ltd | 4. CorruSeal Global | 5. National Paper Mills")

# -----------------------------------------------------------------------------
# TAB 2: VENDOR COMPARISON MATRIX
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Automated Quote Extraction & Normalisation")
    
    uploaded_files = st.file_uploader(
        "Upload incoming vendor quote files (PDF, JPG, PNG, or TXT):",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "txt"]
    )
    if uploaded_files:
        st.success(f"Received {len(uploaded_files)} file(s). Extraction complete.")
    
    st.divider()
    
    # Anomaly Alert Cards
    st.markdown("**AI Detection Flags & Anomalies:**")
    b1, b2, b3 = st.columns(3)
    b1.markdown("<div class='card-warn'>⚠️ BoxCraft: Quoted only 27 of 30 items (Partial Quote)</div>", unsafe_allow_html=True)
    b2.markdown("<div class='card-info'>💱 CorruSeal: Converted from USD to INR (@ 83.5 exchange rate)</div>", unsafe_allow_html=True)
    b3.markdown("<div class='card-danger'>📏 PackTech: Standardised from 'per 100 pcs' to 'per piece'</div>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("**Side-by-Side Normalized Comparison (Click any cell to edit manually):**")
    
    raw_matrix = get_vendor_mock_matrix()
    edited_matrix = st.data_editor(
        raw_matrix,
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    with st.expander("🔍 View Original Document Snippets (Audit Trail)"):
        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown("**Extracted Email Snippet (BoxCraft):**")
            st.code("Attached pricing for items 1-27. For items 28-30, same as last year.", language="text")
        with c_b:
            st.markdown("**AI Extraction Log:**")
            st.write("Flagged items 28-30 as missing. Cells left blank for buyer override.")

# -----------------------------------------------------------------------------
# TAB 3: AI ANALYSIS & AWARD
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Interrogate Bids in Natural Language")
    st.markdown("Select a quick query or type your own question to run scenario analyses across all vendor responses.")
    
    st.markdown("**Suggested CPO Queries:**")
    q1, q2, q3 = st.columns(3)
    
    prompt_choice = None
    if q1.button("💡 Lowest Cost per Item (Split-Award)"):
        prompt_choice = "Show a split-award decision picking the cheapest vendor for each line item. Calculate total cost and savings compared to single vendor."
    if q2.button("⚠️ Check Partial Quote Risks"):
        prompt_choice = "Which vendors failed to quote all items, and what risk does that pose?"
    if q3.button("📊 Recommended Single Vendor"):
        prompt_choice = "Which vendor is best if we must select only one supplier for all 30 items?"

    user_query = st.text_input("Enter your question:", value=prompt_choice if prompt_choice else "", placeholder="e.g., Which vendor offers the best pricing for 5-ply boxes?")
    
    if user_query:
        with st.spinner("Analyzing vendor proposals..."):
            matrix_json = edited_matrix.to_json(orient="records")
            
            system_instruction = """
            You are a chief procurement officer (CPO) assistant.
            Analyze the 30-item vendor matrix and answer clearly in standard English.
            Focus on total spend, calculated savings, and vendor risks.
            Use clear markdown headers and bold numbers.
            """
            
            prompt = f"Data Matrix:\n{matrix_json}\n\nQuestion: {user_query}"
            
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                
                st.markdown("### AI Recommendation")
                st.write(response.text)
                
                st.divider()
                st.markdown("### Total Spend Comparison (INR)")
                
                summary_data = pd.DataFrame({
                    "Vendor": ["Apex", "PackTech", "BoxCraft (Partial)", "CorruSeal", "National Paper"],
                    "Total Estimated Spend (INR)": [1050000, 1020000, 890000, 1120000, 980000]
                })
                fig = px.bar(
                    summary_data, 
                    x="Vendor", 
                    y="Total Estimated Spend (INR)", 
                    color="Vendor",
                    template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                csv = edited_matrix.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Comparison Summary (CSV)",
                    data=csv,
                    file_name="RFx_Vendor_Comparison.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"Error generating analysis: {e}")
