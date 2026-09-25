import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & HIGH-CONTRAST CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | RFx Quote Assistant",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS focused on contrast, readability, and clean UI
st.markdown("""
    <style>
    /* Dark Theme Base */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Fix Unreadable Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #0f172a;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #1e293b !important;
        border-radius: 6px 6px 0px 0px;
        color: #cbd5e1 !important;  /* High contrast light gray text for unselected tabs */
        padding: 8px 18px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284c7 !important; /* Active tab blue */
        color: #ffffff !important;
        font-weight: 700;
    }
    
    /* Custom Info Cards */
    .info-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .info-card h4 {
        color: #38bdf8;
        margin-top: 0;
    }
    
    /* Status Badges */
    .badge-warn {
        background-color: #451a03;
        color: #fcd34d;
        border: 1px solid #78350f;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-info {
        background-color: #0c4a6e;
        color: #7dd3fc;
        border: 1px solid #0369a1;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .badge-danger {
        background-color: #450a0a;
        color: #fca5a5;
        border: 1px solid #7f1d1d;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. SIDEBAR
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("📦 Aerchain Procurement")
    st.caption("Active Project: **Packaging Sourcing 2026**")
    st.divider()
    
    st.markdown("### System Status")
    st.success("🟢 AI Parser: Ready")
    st.info("⚡ Currency Normaliser: Active")
    
    st.divider()
    st.markdown("### Procurement Details")
    st.markdown("""
    * **Category:** Packaging Materials
    * **Total Items:** 30 Line Items
    * **Total Vendors:** 5 Invited
    """)

# Main Header
st.title("RFx Smart Quote Assistant")
st.caption("Automatically standardise vendor quotes, detect pricing anomalies, and compare proposals using AI.")

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
# 5. TABBED INTERFACE WITH CLEAR UX COPY
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "1️⃣ RFx Setup & Items", 
    "2️⃣ Vendor Comparison Table", 
    "3️⃣ AI Analysis & Award Decision"
])

# -----------------------------------------------------------------------------
# TAB 1: RFX SETUP
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("RFx Scope: Corrugated Packaging")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**Master Requirement List (30 Line Items)**")
        # Hide index for cleaner UI
        st.dataframe(get_rfx_baseline(), use_container_width=True, height=420, hide_index=True)
    
    with col2:
        st.markdown("<div class='info-card'>", unsafe_allow_html=True)
        st.markdown("#### Commercial Terms & Quality")
        st.markdown("""
        * **Target Payment Term:** Net 60 Days
        * **Delivery Locations:** Central Warehouses
        * **Quality Certification:** ISO 9001 Mandatory
        * **Defect Limit:** Maximum 0.5%
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='info-card'>", unsafe_allow_html=True)
        st.markdown("#### Invited Vendors (5)")
        st.markdown("""
        1. **Apex Packaging** (Standard PDF)
        2. **PackTech Solutions** (Unit conversion needed)
        3. **BoxCraft Ltd** (Partial quote - 27 items)
        4. **CorruSeal Global** (Quoted in USD)
        5. **National Paper Mills** (Scanned rate sheet)
        """)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# TAB 2: VENDOR COMPARISON
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("Automated Vendor Quote Comparison")
    
    # Upload Area
    uploaded_files = st.file_uploader(
        "Upload vendor quote files (PDF, JPG, PNG, or TXT):",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "txt"]
    )
    if uploaded_files:
        st.success(f"Received {len(uploaded_files)} file(s). Processing through AI parser...")
    
    st.divider()
    
    # Visual Alert Badges (Simple & Clear)
    st.markdown("**AI Detection Flags & Anomalies:**")
    b1, b2, b3 = st.columns(3)
    b1.markdown("<div class='badge-warn'>⚠️ BoxCraft: Quoted only 27 of 30 items</div>", unsafe_allow_html=True)
    b2.markdown("<div class='badge-info'>💱 CorruSeal: Converted from USD to INR (@ 83.5)</div>", unsafe_allow_html=True)
    b3.markdown("<div class='badge-danger'>📏 PackTech: Standardised from 'per 100 pcs' to 'per pc'</div>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("**Comparison Matrix (Click any cell to edit prices manually):**")
    
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
            st.markdown("**AI Action:**")
            st.write("Flagged items 28-30 as missing. Highlighted cells as empty for buyer review.")

# -----------------------------------------------------------------------------
# TAB 3: AI ANALYSIS & AWARD
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("Interrogate Bids with AI")
    st.markdown("Ask questions in plain language to generate split-award scenarios or savings reports.")
    
    # Simple Prompt Options
    st.markdown("**Common Questions:**")
    q1, q2, q3 = st.columns(3)
    
    prompt_choice = None
    if q1.button("💡 Lowest cost per item (Split-Award)"):
        prompt_choice = "Show a split-award decision picking the cheapest vendor for each line item. Calculate total cost and savings compared to single vendor."
    if q2.button("⚠️ Check partial quote risks"):
        prompt_choice = "Which vendors failed to quote all items, and what risk does that pose?"
    if q3.button("📊 Recommended single vendor"):
        prompt_choice = "Which vendor is best if we must select only one supplier for all 30 items?"

    user_query = st.text_input("Type your question here:", value=prompt_choice if prompt_choice else "")
    
    if user_query:
        with st.spinner("Analyzing vendor proposals..."):
            matrix_json = edited_matrix.to_json(orient="records")
            
            system_instruction = """
            You are a procurement advisor helping a category buyer.
            Analyze the 30-item vendor matrix and answer clearly in simple English.
            Focus on total cost, savings, and risks (like missing quotes).
            Use bullet points and bold text for key figures.
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
                
                st.markdown("### Recommendation Summary")
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
                
                # Simple CSV Export
                csv = edited_matrix.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Comparison Summary (CSV)",
                    data=csv,
                    file_name="RFx_Vendor_Comparison.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"Error generating analysis: {e}")
