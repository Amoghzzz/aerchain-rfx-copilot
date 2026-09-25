import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & LIGHT ENTERPRISE DESIGN SYSTEM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | RFx Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enterprise Light Theme Styling
st.markdown("""
    <style>
    /* Global Base */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
    }
    
    /* Hide Default Sidebar */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Top Header Bar */
    .top-bar {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Stage Radio Button Tabs Styling */
    div[data-testid="stHorizontalBlock"] {
        align-items: center;
    }
    
    /* Button Styling */
    .stButton>button {
        background-color: #0284c7 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 8px 16px !important;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #0369a1 !important;
        color: #ffffff !important;
    }

    /* Enterprise Status Cards */
    .status-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .badge-ok {
        color: #15803d;
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-warn {
        color: #b45309;
        background-color: #fefce8;
        border: 1px solid #fef08a;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-alert {
        color: #b91c1c;
        background-color: #fef2f2;
        border: 1px solid #fecaca;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.8rem;
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
# 3. MOCK DATASETS & DETERMINISTIC CALCULATIONS ENGINE
# -----------------------------------------------------------------------------
@st.cache_data
def get_rfx_baseline():
    categories = ["5-Ply Heavy Duty Box", "3-Ply Standard Box", "Custom Printed Mailer", "Partition Tray"]
    items = []
    for i in range(1, 31):
        cat = categories[(i - 1) % len(categories)]
        items.append({
            "Line #": f"ITEM-{i:03d}",
            "Description": f"{cat} - Spec Variant {i}",
            "Target Qty": (i * 500) + 1000,
            "UOM": "pcs",
            "Specification": "180 GSM Kraft Paper" if i % 2 == 0 else "150 GSM Kraft Paper"
        })
    return pd.DataFrame(items)

@st.cache_data
def get_vendor_mock_matrix():
    base_df = get_rfx_baseline().copy()
    
    # Fabricated vendor pricing demonstrating edge cases
    base_df["Vendor A (INR)"] = [round(20 + (i * 0.8), 2) for i in range(30)]
    base_df["Vendor B (INR)"] = [round(18 + (i * 0.75), 2) if i < 27 else None for i in range(30)] # Partial
    base_df["Vendor C (USD->INR)"] = [round((0.23 + (i * 0.01)) * 83.5, 2) for i in range(30)] # Currency
    base_df["Vendor D (INR)"] = [round(19 + (i * 0.85), 2) for i in range(30)] # Unit normalized
    base_df["Vendor E (INR)"] = [round(22 + (i * 0.7), 2) for i in range(30)] # Scanned OCR
    
    return base_df

@st.cache_data
def get_questionnaire_matrix():
    data = {
        "Evaluation Metric": [
            "ISO 9001 Certified?",
            "FSC Certification attached?",
            "3-Year Rejection Rate",
            "Monthly Capacity (Units)",
            "Payment Terms Offered",
            "Quality Status"
        ],
        "Vendor A": ["YES", "YES", "0.8%", "1.2M", "Net 60", "PASSED"],
        "Vendor B": ["YES", "NO", "1.4%", "900K", "Net 30", "PASSED"],
        "Vendor C": ["YES", "YES", "0.5%", "1.5M", "Net 60", "PASSED"],
        "Vendor D": ["NO", "YES", "2.1%", "1.1M", "Net 45", "FAILED (Quality)"],
        "Vendor E": ["YES", "YES", "1.2%", "1.3M", "Net 30", "PASSED"]
    }
    return pd.DataFrame(data)

# Deterministic Mathematical Calculation Function
def calculate_split_award_metrics(df):
    vendor_cols = ["Vendor A (INR)", "Vendor B (INR)", "Vendor C (USD->INR)", "Vendor D (INR)", "Vendor E (INR)"]
    
    # Exclude Vendor D (Failed Quality) and Vendor B for missing rows if evaluating complete quotes
    valid_cols = ["Vendor A (INR)", "Vendor C (USD->INR)", "Vendor E (INR)"]
    
    # Calculate baseline single vendor total spend
    single_vendor_totals = {}
    for col in vendor_cols:
        sum_val = (df[col] * df["Target Qty"]).sum()
        single_vendor_totals[col] = round(sum_val, 2)
        
    best_single_vendor = min(single_vendor_totals, key=single_vendor_totals.get)
    best_single_spend = single_vendor_totals[best_single_vendor]
    
    # Calculate lowest cost line item split (among quality-qualified vendors)
    df["Min_Price"] = df[valid_cols].min(axis=1)
    df["Lowest_Vendor"] = df[valid_cols].idxmin(axis=1)
    split_award_spend = round((df["Min_Price"] * df["Target Qty"]).sum(), 2)
    
    potential_savings = round(best_single_spend - split_award_spend, 2)
    savings_pct = round((potential_savings / best_single_spend) * 100, 1)
    
    return {
        "best_single_vendor": best_single_vendor.split(" ")[0],
        "best_single_spend": best_single_spend,
        "split_award_spend": split_award_spend,
        "potential_savings": potential_savings,
        "savings_pct": savings_pct,
        "split_details": df[["Line #", "Description", "Target Qty", "Lowest_Vendor", "Min_Price"]]
    }

# -----------------------------------------------------------------------------
# 4. TOP WORKSPACE HEADER & NAVIGATION
# -----------------------------------------------------------------------------
st.markdown("""
<div class="top-bar">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <strong style="font-size: 1.15rem; color: #0f172a;">AERCHAIN</strong>
            <span style="color: #64748b; font-size: 0.9rem; margin-left: 8px;">| RFx Sourcing Workspace</span>
        </div>
        <div>
            <span style="color: #64748b; font-size: 0.85rem;">Project:</span> 
            <strong style="color: #0f172a;">Corrugated Packaging 2026</strong>
            <span style="color: #cbd5e1; margin: 0 8px;">•</span>
            <span style="color: #64748b; font-size: 0.85rem;">Scope:</span> 
            <strong style="color: #0284c7;">30 Items | 5 Vendors</strong>
        </div>
        <div>
            <span class="badge-ok">● Pipeline Active</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation Stage Bar
nav_stage = st.radio(
    "Navigation:",
    ["① RFx", "② Responses", "③ Comparison", "④ Analysis"],
    horizontal=True,
    label_visibility="collapsed"
)

st.divider()

# -----------------------------------------------------------------------------
# STAGE 1: RFX
# -----------------------------------------------------------------------------
if nav_stage == "① RFx":
    st.subheader("RFx Setup & Scope Ground Truth")
    st.caption("Tell us what you are sourcing. The AI co-pilot structures the scope, 30 line items, and terms.")
    
    prompt_input = st.text_area(
        "Describe your procurement requirement:",
        value="I need to source corrugated packaging boxes for North India operations. Around 30 line items across 5-ply and 3-ply boxes. Require ISO 9001 certified suppliers with Net 60 payment terms.",
        height=90
    )
    
    if st.button("Generate RFx Structure"):
        st.success("RFx successfully generated and mapped.")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("**Master Requirement List (30 Line Items)**")
        st.dataframe(get_rfx_baseline(), use_container_width=True, height=360, hide_index=True)
    with c2:
        st.markdown("**Commercial Terms & Requirements**")
        st.info("""
        * **Category:** Packaging Materials
        * **Target Currency:** INR
        * **Response Deadline:** 15 Oct 2026
        * **Invited Vendors (5):** Vendor A, Vendor B, Vendor C, Vendor D, Vendor E
        * **Mandatory Criteria:** ISO 9001 Certification, <0.5% Defect Rate, Net 60 Terms
        """)

# -----------------------------------------------------------------------------
# STAGE 2: RESPONSES
# -----------------------------------------------------------------------------
elif nav_stage == "② Responses":
    st.subheader("Vendor Document Ingestion & Verification")
    st.caption("Review extracted vendor files and audit AI normalization across messy submission formats.")
    
    st.markdown("**Ingestion Processing Status:**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.markdown("<div class='status-card'><span class='badge-ok'>Vendor A</span><br><br><b>Clean Excel</b><br>30/30 Extracted</div>", unsafe_allow_html=True)
    m2.markdown("<div class='status-card'><span class='badge-warn'>Vendor B</span><br><br><b>PDF Document</b><br>27/30 Extracted</div>", unsafe_allow_html=True)
    m3.markdown("<div class='status-card'><span class='badge-ok'>Vendor C</span><br><br><b>Excel (USD)</b><br>30/30 Extracted</div>", unsafe_allow_html=True)
    m4.markdown("<div class='status-card'><span class='badge-alert'>Vendor D</span><br><br><b>Word Doc</b><br>Unit Normalised</div>", unsafe_allow_html=True)
    m5.markdown("<div class='status-card'><span class='badge-warn'>Vendor E</span><br><br><b>Scanned OCR</b><br>3 Fields Review</div>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("### Extraction Audit Trail (Side-by-Side Review)")
    
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.markdown("**Original Vendor Quote Snippet (Vendor B Quote.pdf):**")
        st.code("""
        =====================================================
        PACKAGING BID RESPONSE - VENDOR B
        Quote Ref: VB-2026-99
        
        Items 1 to 27: Quoted as per specifications attached.
        Items 28, 29, 30: Out of stock. Not quoting.
        =====================================================
        """, language="text")
    
    with col_b:
        st.markdown("**AI Extraction & Verification Metadata:**")
        st.json({
            "vendor": "Vendor B",
            "extracted_lines": "27 / 30",
            "missing_lines": ["ITEM-028", "ITEM-029", "ITEM-030"],
            "unit_of_measure": "pcs",
            "confidence": "94%",
            "system_flag": "Incomplete Quote - Exception Flagged"
        })
        st.button("Confirm Verification & Save")

# -----------------------------------------------------------------------------
# STAGE 3: COMPARISON
# -----------------------------------------------------------------------------
elif nav_stage == "③ Comparison":
    st.subheader("Side-by-Side Comparison Workspace")
    st.caption("Normalized pricing, commercial terms, and qualitative evaluations sitting alongside the numbers.")
    
    view_mode = st.radio("Select View:", ["Commercial Pricing Matrix", "Qualitative Questionnaire Matrix"], horizontal=True)
    
    if view_mode == "Commercial Pricing Matrix":
        st.markdown("**Commercials Comparison Grid (Double-click any cell to override):**")
        matrix_df = get_vendor_mock_matrix()
        edited_matrix = st.data_editor(
            matrix_df,
            use_container_width=True,
            height=420,
            hide_index=True
        )
    else:
        st.markdown("**Vendor Qualitative Criteria & Compliance:**")
        q_df = get_questionnaire_matrix()
        st.dataframe(q_df, use_container_width=True, height=280, hide_index=True)

# -----------------------------------------------------------------------------
# STAGE 4: ANALYSIS
# -----------------------------------------------------------------------------
elif nav_stage == "④ Analysis":
    st.subheader("Explore Your Bids")
    st.caption("Ask questions, compare scenarios, and understand the trade-offs before you award.")
    
    # Calculate deterministic baseline math
    raw_matrix = get_vendor_mock_matrix()
    calc = calculate_split_award_metrics(raw_matrix)
    
    # Deterministic KPI Summary Bar
    st.markdown("**Calculated Sourcing Metrics:**")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Lowest Single Vendor", f"₹{calc['best_single_spend']:,.0f}", f"Vendor {calc['best_single_vendor']}")
    k2.metric("Split-Award Total", f"₹{calc['split_award_spend']:,.0f}", f"-₹{calc['potential_savings']:,.0f}")
    k3.metric("Potential Savings", f"{calc['savings_pct']}%", "vs Single Vendor")
    k4.metric("Qualified Vendors", "3 / 5", "Vendor D Failed Quality")
    
    st.divider()
    
    # Quick Prompt Buttons
    st.markdown("**Suggested Queries:**")
    q1, q2, q3 = st.columns(3)
    
    prompt_choice = None
    if q1.button("💡 Analyze lowest-cost split award"):
        prompt_choice = f"Explain the split-award scenario where total spend is ₹{calc['split_award_spend']:,.0f} compared to single vendor spend of ₹{calc['best_single_spend']:,.0f}. Which vendors get which line items?"
    if q2.button("⚠️ Evaluate vendor risk & missing quotes"):
        prompt_choice = "Which vendors pose operational risks due to incomplete quotes or failed quality certifications?"
    if q3.button("📊 Single vendor award recommendation"):
        prompt_choice = "Which single vendor offers the best overall proposal if we cannot split the award across multiple suppliers?"

    user_query = st.text_input("Type your question:", value=prompt_choice if prompt_choice else "", placeholder="e.g., Show line items where Vendor C is >10% cheaper than Vendor A.")
    
    if user_query:
        with st.spinner("Analyzing dataset with Gemini 2.5 Flash..."):
            matrix_json = raw_matrix.to_json(orient="records")
            q_json = get_questionnaire_matrix().to_json(orient="records")
            
            system_instruction = f"""
            You are an expert Chief Procurement Officer (CPO) assistant.
            You are analyzing an RFx dataset of 30 line items across 5 vendors.
            
            Deterministic Pre-Calculated Baseline:
            - Best Single-Vendor Award: Vendor {calc['best_single_vendor']} at ₹{calc['best_single_spend']:,.0f}
            - Lowest Line-Item Split Award: ₹{calc['split_award_spend']:,.0f}
            - Calculated Savings: ₹{calc['potential_savings']:,.0f} ({calc['savings_pct']}%)
            - Vendor D failed quality standards. Vendor B missed 3 line items.
            
            Provide a clear executive response in plain English using markdown headers, bullet points, and explicit trade-off explanations.
            """
            
            prompt = f"Data Matrix:\n{matrix_json}\n\nQuality Matrix:\n{q_json}\n\nUser Question: {user_query}"
            
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                
                st.markdown("### Executive Advisory Summary")
                st.write(response.text)
                
                st.divider()
                st.markdown("### Spend Comparison Visualizer")
                
                summary_data = pd.DataFrame({
                    "Vendor": ["Vendor A", "Vendor B (Partial)", "Vendor C (USD->INR)", "Vendor D (Failed Quality)", "Vendor E"],
                    "Total Quoted Spend (INR)": [1050000, 890000, 1020000, 1120000, 980000]
                })
                fig = px.bar(
                    summary_data, 
                    x="Vendor", 
                    y="Total Quoted Spend (INR)", 
                    color="Vendor",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    template="plotly_white",
                    title="Total Quoted Spend Comparison Across All 5 Suppliers"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # CSV Export
                csv = raw_matrix.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Decision Summary & Comparison Grid (CSV)",
                    data=csv,
                    file_name="RFx_Award_Decision_Summary.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"Error querying Gemini API: {e}")
