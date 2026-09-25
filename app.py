import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & MASTER SAAS STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | AI Procurement Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom High-Contrast Enterprise CSS
st.markdown("""
    <style>
    /* Dark Slate Base Theme */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Hide Default Sidebar */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Top Navigation Header */
    .nav-header {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 24px;
        margin-bottom: 24px;
    }
    
    /* Stage Navigation Radio Styling */
    div[data-testid="stHorizontalBlock"] {
        align-items: center;
    }
    
    /* Button Customization - Ensure Crisp Dark Text on Light Buttons */
    .stButton>button {
        background-color: #38bdf8 !important;
        color: #0f172a !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 10px 18px !important;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #7dd3fc !important;
        color: #0f172a !important;
    }

    /* Exception & Alert Badges */
    .badge-warn {
        background-color: #451a03;
        color: #fde047;
        border: 1px solid #a16207;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-info {
        background-color: #0c4a6e;
        color: #7dd3fc;
        border: 1px solid #0284c7;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-danger {
        background-color: #450a0a;
        color: #fca5a5;
        border: 1px solid #9f1239;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    </style>
""", unsafe_allow_html=True)

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
    st.error(f"Failed to connect to Vertex AI engine: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. DATA SCHEMAS & MOCK ENGINE (5 Fabricated Vendors with Ugly Edge Cases)
# -----------------------------------------------------------------------------
@st.cache_data
def get_rfx_baseline():
    categories = ["5-Ply Heavy Box", "3-Ply Standard Box", "Custom Printed Mailer", "Partition Tray"]
    items = []
    for i in range(1, 31):
        cat = categories[(i - 1) % len(categories)]
        items.append({
            "Item #": f"ITEM-{i:03d}",
            "Specification": f"{cat} - Spec Variant {i}",
            "Target Qty": (i * 500) + 1000,
            "Target UOM": "pcs",
            "Target Spec": "180 GSM Kraft" if i % 2 == 0 else "150 GSM Kraft"
        })
    return pd.DataFrame(items)

@st.cache_data
def get_vendor_mock_matrix():
    base_df = get_rfx_baseline().copy()
    
    # Vendor A: Clean Excel (INR)
    base_df["Vendor A (INR/pc)"] = [round(20 + (i * 0.8), 2) for i in range(30)]
    
    # Vendor B: Incomplete PDF (27/30 lines)
    base_df["Vendor B (INR/pc)"] = [round(18 + (i * 0.75), 2) if i < 27 else None for i in range(30)]
    
    # Vendor C: Excel in USD (Converted to INR @ 83.5)
    base_df["Vendor C (USD->INR)"] = [round((0.23 + (i * 0.01)) * 83.5, 2) for i in range(30)]
    
    # Vendor D: Word Doc (Ambiguous units: Quoted per 100 pcs -> Normalized to per pc)
    base_df["Vendor D (Normalized)"] = [round(19 + (i * 0.85), 2) for i in range(30)]
    
    # Vendor E: Scanned Image (OCR low confidence on 3 lines)
    base_df["Vendor E (Scanned OCR)"] = [round(22 + (i * 0.7), 2) for i in range(30)]
    
    return base_df

@st.cache_data
def get_questionnaire_matrix():
    data = {
        "Criteria / Question": [
            "ISO 9001 Certified?",
            "FSC Certification attached?",
            "3-Year Rejection Rate",
            "Monthly Capacity (Units)",
            "Payment Terms Offered",
            "Freight Responsibility"
        ],
        "Vendor A": ["YES", "YES", "0.8%", "1.2M", "Net 60", "Vendor Prepaid"],
        "Vendor B": ["YES", "NO", "1.4%", "900K", "Net 30", "Buyer Collect"],
        "Vendor C": ["YES", "YES", "0.5%", "1.5M", "Net 60", "Vendor Prepaid"],
        "Vendor D": ["NO", "YES", "2.1%", "1.1M", "Net 45", "Vendor Prepaid"],
        "Vendor E": ["YES", "YES", "1.2%", "1.3M", "Net 30", "Buyer Collect"]
    }
    return pd.DataFrame(data)

# -----------------------------------------------------------------------------
# 4. TOP WORKSPACE HEADER & STAGE NAVIGATION
# -----------------------------------------------------------------------------
st.markdown("""
<div class="nav-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <span style="color: #38bdf8; font-weight: 700; font-size: 1.2rem;">AERCHAIN</span>
            <span style="color: #94a3b8; font-size: 0.9rem; margin-left: 12px;">| AI Sourcing Workspace</span>
        </div>
        <div>
            <span style="color: #f8fafc; font-weight: 600;">Event:</span> 
            <span style="color: #38bdf8;">Corrugated Packaging Sourcing 2026</span>
            <span style="color: #64748b; margin: 0 8px;">•</span>
            <span style="color: #f8fafc; font-weight: 600;">Scope:</span> 30 Items | 5 Vendors
        </div>
        <div>
            <span style="color: #4ade80; font-weight: 600;">● Engine Active</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 4 Primary Stage Navigation Tabs
nav_stage = st.radio(
    "Select Stage:",
    ["① RFx Creation", "② Vendor Responses & Extraction", "③ Comparison Workspace", "④ AI Analyst & Award"],
    horizontal=True,
    label_visibility="collapsed"
)

st.divider()

# -----------------------------------------------------------------------------
# STAGE 1: RFX CREATION
# -----------------------------------------------------------------------------
if nav_stage == "① RFx Creation":
    st.subheader("Stage 1: Generate RFx with AI Co-Pilot")
    st.caption("Describe your procurement needs in natural language. The system will structure the scope, line items, and terms.")
    
    prompt_input = st.text_area(
        "Describe what you are sourcing:",
        value="I need to source corrugated packaging boxes for our North India warehouses. Around 30 SKUs across 5-ply and 3-ply boxes. Require ISO 9001 certified vendors with Net 60 payment terms.",
        height=100
    )
    
    if st.button("✨ Structure RFx Scope"):
        st.success("RFx generated successfully!")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("**Structured Line Items Schema (30 Items)**")
        st.dataframe(get_rfx_baseline(), use_container_width=True, height=350, hide_index=True)
    with c2:
        st.markdown("**Commercial Terms & Questionnaire**")
        st.info("""
        * **Category:** Packaging Materials
        * **Currency Target:** INR
        * **Response Deadline:** 15 Oct 2026
        * **Invited Vendors (5):** Vendor A, Vendor B, Vendor C, Vendor D, Vendor E
        * **Mandatory Questions:** ISO 9001 Certification, Rejection Rate, Payment Terms
        """)

# -----------------------------------------------------------------------------
# STAGE 2: VENDOR RESPONSES & EXTRACTION REVIEW
# -----------------------------------------------------------------------------
elif nav_stage == "② Vendor Responses & Extraction":
    st.subheader("Stage 2: Vendor Document Extraction & Verification")
    st.caption("Upload raw vendor quotes. The AI processes heterogeneous formats and highlights extraction anomalies.")
    
    # Processing Status Cards
    st.markdown("**Ingested Vendor Documents & Anomaly Tracker:**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.markdown("<div class='badge-info'><b>Vendor A</b><br>✓ Clean Excel<br>30/30 Extracted</div>", unsafe_allow_html=True)
    m2.markdown("<div class='badge-warn'><b>Vendor B</b><br>⚠ PDF (Incomplete)<br>27/30 Extracted</div>", unsafe_allow_html=True)
    m3.markdown("<div class='badge-info'><b>Vendor C</b><br>💱 Excel (USD)<br>30/30 Extracted</div>", unsafe_allow_html=True)
    m4.markdown("<div class='badge-danger'><b>Vendor D</b><br>📏 Word Doc<br>3 Unit Normalizations</div>", unsafe_allow_html=True)
    m5.markdown("<div class='badge-warn'><b>Vendor E</b><br>🔍 Scanned Image<br>3 Low-Confidence OCR</div>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("### Verification Drawer: Inspect Extraction Reasoning")
    
    # Split Screen Extraction Verification
    v_col1, v_col2 = st.columns([1, 1])
    with v_col1:
        st.markdown("**Original Vendor Document Snippet (Vendor B Quote.pdf):**")
        st.code("""
        =====================================================
        PACKAGING BID RESPONSE - VENDOR B
        Quote Reference: VB-2026-99
        
        Items 1 to 27: Quoted as per specifications attached.
        Items 28, 29, 30: Out of stock. Not quoting.
        =====================================================
        """, language="text")
    
    with v_col2:
        st.markdown("**AI Extraction & Confidence Audit:**")
        st.json({
            "vendor": "Vendor B",
            "extracted_fields": "27 / 30",
            "missing_lines": ["ITEM-028", "ITEM-029", "ITEM-030"],
            "unit_of_measure": "pcs",
            "confidence_score": "94%",
            "system_flag": "Incomplete Quote - High Risk"
        })
        st.button("Accept Verification & Proceed")

# -----------------------------------------------------------------------------
# STAGE 3: COMPARISON WORKSPACE
# -----------------------------------------------------------------------------
elif nav_stage == "③ Comparison Workspace":
    st.subheader("Stage 3: Side-by-Side Comparison Workspace")
    st.caption("Hero View: Normalized pricing, commercial terms, and qualitative questionnaire side-by-side.")
    
    comp_mode = st.radio("View Comparison Layer:", ["Commercial Matrix (Pricing)", "Quality & Compliance Questionnaire", "Source Audit Log"], horizontal=True)
    
    if comp_mode == "Commercial Matrix (Pricing)":
        st.markdown("**Side-by-Side Normalized Commercials (Click cell to edit):**")
        matrix_df = get_vendor_mock_matrix()
        edited_df = st.data_editor(
            matrix_df,
            use_container_width=True,
            height=420,
            hide_index=True
        )
    elif comp_mode == "Quality & Compliance Questionnaire":
        st.markdown("**Vendor Qualitative Criteria Evaluation:**")
        q_df = get_questionnaire_matrix()
        st.dataframe(q_df, use_container_width=True, height=300, hide_index=True)
    else:
        st.markdown("**Traceability & Lineage Log:**")
        st.info("Every extracted number is anchored to its source file snippet. Click any row in the comparison grid to trace back to source PDF/Excel cell references.")

# -----------------------------------------------------------------------------
# STAGE 4: AI ANALYST & AWARD
# -----------------------------------------------------------------------------
elif nav_stage == "④ AI Analyst & Award":
    st.subheader("Stage 4: Conversational Decision Intelligence")
    st.caption("Ask complex questions across the normalized dataset to generate split-award scenarios, charts, and recommendations.")
    
    st.markdown("**Suggested CPO Analysis Questions:**")
    q1, q2, q3 = st.columns(3)
    
    prompt_choice = None
    if q1.button("💡 Split-Award: Lowest price per item"):
        prompt_choice = "What if I split the order by line item among vendors who passed quality? Show total cost and savings."
    if q2.button("⚠️ Audit Partial Quote Risks"):
        prompt_choice = "Which vendors have missing quotes or currency mismatches, and what is the spend risk?"
    if q3.button("📊 Recommended Single Vendor"):
        prompt_choice = "Which single vendor offers the best overall value considering quality and price?"

    user_query = st.text_input("Ask a question about the bids:", value=prompt_choice if prompt_choice else "", placeholder="e.g., Show me items where Vendor C is >10% cheaper than Vendor A.")
    
    if user_query:
        with st.spinner("Calculating scenarios with Gemini 2.5 Flash..."):
            matrix_json = get_vendor_mock_matrix().to_json(orient="records")
            q_json = get_questionnaire_matrix().to_json(orient="records")
            
            system_instruction = """
            You are a Chief Procurement Officer AI assistant.
            Analyze the normalized matrix and questionnaire.
            When asked scenario questions (e.g. split-award), provide structured output:
            1. Executive Savings Summary
            2. Split-Award Allocation Table (Vendor, Items Awarded, Value)
            3. Explicit Assumptions (e.g. Quality filtering, Unit conversions)
            Use clear markdown tables, bold metrics, and concise bullet points.
            """
            
            prompt = f"Commercial Matrix:\n{matrix_json}\n\nQuality Questionnaire:\n{q_json}\n\nQuestion: {user_query}"
            
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                
                st.markdown("### AI Analyst Decision Intelligence")
                st.write(response.text)
                
                st.divider()
                st.markdown("### Commercial Spend Distribution (INR)")
                
                summary_data = pd.DataFrame({
                    "Vendor": ["Vendor A", "Vendor B (Partial)", "Vendor C (USD->INR)", "Vendor D", "Vendor E"],
                    "Total Spend (INR)": [1050000, 890000, 1020000, 1120000, 980000]
                })
                fig = px.bar(
                    summary_data, 
                    x="Vendor", 
                    y="Total Spend (INR)", 
                    color="Vendor",
                    template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                csv = get_vendor_mock_matrix().to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Decision Note & Extraction Matrix (CSV)",
                    data=csv,
                    file_name="RFx_Decision_Summary.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"Error querying Gemini API: {e}")
