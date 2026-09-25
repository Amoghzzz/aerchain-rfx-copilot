import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & ENTERPRISE LIGHT THEME (CSS)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | Enterprise RFQ Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Enterprise Light Theme Styling
st.markdown("""
    <style>
    /* Global Base Light Theme */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Hide Default Sidebar Completely */
    [data-testid="stSidebar"] {
        display: none;
    }
    
    /* Header Card & Context Banner */
    .top-context-bar {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    
    /* Stage Header Text & Step Pills */
    .stage-pill-active {
        background-color: #0284c7;
        color: #ffffff;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .stage-pill-done {
        background-color: #e0f2fe;
        color: #0369a1;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    
    /* Cards & Containers */
    .procurement-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    
    /* Status Badges & Trust Labels */
    .badge-success {
        background-color: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .badge-amber {
        background-color: #fffbeb;
        color: #b45309;
        border: 1px solid #fef08a;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .badge-red {
        background-color: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    
    /* AI Lineage & Origin Tags */
    .tag-user {
        background-color: #f1f5f9;
        color: #334155;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .tag-ai-extracted {
        background-color: #f0f9ff;
        color: #0369a1;
        border: 1px solid #bae6fd;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .tag-ai-inferred {
        background-color: #faf5ff;
        color: #7e22ce;
        border: 1px solid #e9d5ff;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* Streamlit Button Styling Overrides */
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
    
    /* Streamlit Radio Header Customization */
    div[data-testid="stHorizontalBlock"] {
        align-items: center;
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
    st.error(f"Failed to connect to AI engine: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. DATA SCHEMAS & DETERMINISTIC CALCULATIONS
# -----------------------------------------------------------------------------
@st.cache_data
def get_rfx_baseline():
    categories = ["5-Ply Heavy Duty Box", "3-Ply Standard Box", "Custom Printed Mailer", "Corrugated Partition Tray"]
    items = []
    for i in range(1, 31):
        cat = categories[(i - 1) % len(categories)]
        items.append({
            "Line #": f"ITEM-{i:03d}",
            "Description": f"{cat} - Spec Variant {i}",
            "Quantity": (i * 500) + 1000,
            "UOM": "pcs",
            "Specification": "180 GSM Kraft Paper" if i % 2 == 0 else "150 GSM Kraft Paper",
            "Status": "Confirmed" if i <= 27 else "Needs Confirmation"
        })
    return pd.DataFrame(items)

@st.cache_data
def get_vendor_mock_matrix():
    base_df = get_rfx_baseline().copy()
    
    # Fabricated vendor pricing demonstrating edge cases[cite: 1]
    base_df["Apex Packaging (INR)"] = [round(20 + (i * 0.8), 2) for i in range(30)]
    base_df["PackTech Solutions (INR)"] = [round(19 + (i * 0.85), 2) for i in range(30)] # Unit normalized[cite: 1]
    base_df["BoxCraft Ltd (INR)"] = [round(18 + (i * 0.75), 2) if i < 27 else None for i in range(30)] # Partial quote[cite: 1]
    base_df["CorruSeal Global (USD->INR)"] = [round((0.23 + (i * 0.01)) * 83.5, 2) for i in range(30)] # Currency mismatch[cite: 1]
    base_df["National Paper Mills (INR)"] = [round(22 + (i * 0.7), 2) for i in range(30)] # Scanned rate card[cite: 1]
    
    return base_df

@st.cache_data
def get_questionnaire_matrix():
    data = {
        "Evaluation Metric": [
            "ISO 9001 Certification",
            "FSC Certification",
            "3-Year Defect Rate",
            "Monthly Capacity",
            "Payment Terms",
            "Freight Responsibility",
            "Compliance Status"
        ],
        "Apex Packaging": ["YES", "YES", "0.8%", "1.2M pcs", "Net 60", "Supplier Prepaid", "Meets Requirement"],
        "PackTech Solutions": ["NO", "YES", "2.1%", "1.1M pcs", "Net 45", "Supplier Prepaid", "Requires Attention"],
        "BoxCraft Ltd": ["YES", "NO", "1.4%", "900K pcs", "Net 30", "Buyer Collect", "Requires Attention"],
        "CorruSeal Global": ["YES", "YES", "0.5%", "1.5M pcs", "Net 60", "Supplier Prepaid", "Meets Requirement"],
        "National Paper Mills": ["YES", "YES", "1.2%", "1.3M pcs", "Net 30", "Buyer Collect", "Meets Requirement"]
    }
    return pd.DataFrame(data)

def calculate_split_award_metrics(df):
    supplier_cols = [
        "Apex Packaging (INR)", "PackTech Solutions (INR)", 
        "BoxCraft Ltd (INR)", "CorruSeal Global (USD->INR)", "National Paper Mills (INR)"
    ]
    
    # Qualified suppliers only (excluding partial and non-compliant)
    valid_cols = ["Apex Packaging (INR)", "CorruSeal Global (USD->INR)", "National Paper Mills (INR)"]
    
    single_totals = {}
    for col in supplier_cols:
        sum_val = (df[col] * df["Quantity"]).sum()
        single_totals[col] = round(sum_val, 2) if not pd.isna(sum_val) else float('inf')
        
    best_single_supplier = min(single_totals, key=single_totals.get)
    best_single_spend = single_totals[best_single_supplier]
    
    df["Min_Price"] = df[valid_cols].min(axis=1)
    df["Lowest_Supplier"] = df[valid_cols].idxmin(axis=1)
    split_spend = round((df["Min_Price"] * df["Quantity"]).sum(), 2)
    
    savings = round(best_single_spend - split_spend, 2)
    savings_pct = round((savings / best_single_spend) * 100, 1) if best_single_spend > 0 else 0
    
    return {
        "best_single_supplier": best_single_supplier.split(" (")[0],
        "best_single_spend": best_single_spend,
        "split_spend": split_spend,
        "savings": savings,
        "savings_pct": savings_pct
    }

# -----------------------------------------------------------------------------
# 4. PERSISTENT RFQ CONTEXT BANNER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="top-context-bar">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div>
            <span style="font-size: 0.78rem; text-transform: uppercase; color: #64748b; font-weight: 700;">RFQ Reference</span><br>
            <strong style="font-size: 1.05rem; color: #0f172a;">RFQ-2026-PKG-001</strong>
        </div>
        <div>
            <span style="font-size: 0.78rem; text-transform: uppercase; color: #64748b; font-weight: 700;">Project Name</span><br>
            <span style="font-size: 0.95rem; font-weight: 600; color: #0284c7;">Corrugated Packaging Sourcing</span>
        </div>
        <div>
            <span style="font-size: 0.78rem; text-transform: uppercase; color: #64748b; font-weight: 700;">Scope</span><br>
            <span style="font-size: 0.95rem; font-weight: 600; color: #334155;">30 Line Items</span>
        </div>
        <div>
            <span style="font-size: 0.78rem; text-transform: uppercase; color: #64748b; font-weight: 700;">Suppliers</span><br>
            <span style="font-size: 0.95rem; font-weight: 600; color: #334155;">5 Invited (5 Responded)</span>
        </div>
        <div>
            <span style="font-size: 0.78rem; text-transform: uppercase; color: #64748b; font-weight: 700;">Deadline</span><br>
            <span style="font-size: 0.95rem; font-weight: 600; color: #334155;">15 Oct 2026</span>
        </div>
        <div>
            <span style="font-size: 0.78rem; text-transform: uppercase; color: #64748b; font-weight: 700;">Exceptions</span><br>
            <span class="badge-amber">7 Items Require Attention</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 5. WORKFLOW STAGE NAVIGATION
# -----------------------------------------------------------------------------
stage = st.radio(
    "Procurement Workflow Stage:",
    ["Create RFQ", "Supplier Responses", "Compare Bids", "Analyze & Decide"],
    horizontal=True,
    label_visibility="collapsed"
)

st.divider()

# -----------------------------------------------------------------------------
# STAGE 1: CREATE RFQ
# -----------------------------------------------------------------------------
if stage == "Create RFQ":
    st.subheader("What are you looking to procure?")
    st.caption("Provide your procurement requirements in plain language. The AI assistant will structure the scope, specifications, and terms.")
    
    req_input = st.text_area(
        "Procurement Requirements Input",
        value="I need to source corrugated packaging boxes for our North India manufacturing plants. Around 30 SKUs across 5-ply and 3-ply heavy duty boxes. Require ISO 9001 certified suppliers with Net 60 payment terms and delivery to Bhiwandi and Hosur warehouses.",
        height=100,
        placeholder="e.g. Sourcing 30 line items of industrial packaging materials with Net 60 payment terms..."
    )
    
    if st.button("Generate RFQ Proposal"):
        st.success("RFQ scope generated successfully.")
    
    st.write("")
    
    # Structured AI Summary Breakdown
    st.markdown("### Executive RFQ Summary")
    
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**User Provided Information** <span class='tag-user'>Verified</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Category:** Packaging Materials
        * **Target Lines:** 30 Line Items
        * **Target Terms:** Net 60 Days
        * **Locations:** Bhiwandi & Hosur Warehouses
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with s2:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**AI Identified Specifications** <span class='tag-ai-extracted'>Extracted</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Material Specs:** 180 GSM / 150 GSM Kraft Paper
        * **Quality Certification:** ISO 9001 Mandatory
        * **Defect Limit:** < 0.5% Tolerance
        * **Target Currency:** INR
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with s3:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Needs Confirmation** <span class='badge-amber'>Action Required</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Price Validity Period:** Unspecified (Recommend 60 days)
        * **Freight Ownership:** Unspecified (Incoterms needed)
        * **Line Items 28-30:** Quantity specs require validation
        * **Buffer Delivery Lead Time:** Unspecified
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown("### Master Line Items Table (30 Items)")
    
    # Line Item Filters
    col_search, col_filter = st.columns([2, 1])
    with col_search:
        search_query = st.text_input("Search Line Items:", placeholder="e.g. 5-Ply Heavy Duty")
    with col_filter:
        status_filter = st.selectbox("Filter Status:", ["All Items", "Confirmed", "Needs Confirmation"])
        
    df_items = get_rfx_baseline()
    if search_query:
        df_items = df_items[df_items["Description"].str.contains(search_query, case=False)]
    if status_filter != "All Items":
        df_items = df_items[df_items["Status"] == status_filter]
        
    st.dataframe(df_items, use_container_width=True, height=360, hide_index=True)
    
    col_pub1, col_pub2 = st.columns([4, 1])
    with col_pub2:
        if st.button("Publish RFQ to 5 Suppliers"):
            st.balloons()
            st.success("RFQ Published!")

# -----------------------------------------------------------------------------
# STAGE 2: SUPPLIER RESPONSES
# -----------------------------------------------------------------------------
elif stage == "Supplier Responses":
    st.subheader("Supplier Response Inbox")
    st.caption("Review incoming supplier quote submissions, extraction status, and system-identified exceptions.")
    
    # Inbox Metric Bar
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Suppliers Invited", "5")
    m2.metric("Responses Received", "5 / 5")
    m3.metric("Responses Pending", "0")
    m4.metric("Exceptions for Review", "7", delta="Requires Review", delta_color="inverse")
    
    st.write("")
    st.markdown("### Submission Summary & Extraction Status")
    
    supplier_inbox = [
        {"Supplier": "Apex Packaging", "File Format": "Excel (.xlsx)", "Items Extracted": "30 / 30", "Confidence": "98%", "Currency": "INR", "Status": "Complete", "Exceptions": "None"},
        {"Supplier": "PackTech Solutions", "File Format": "Word (.docx)", "Items Extracted": "30 / 30", "Confidence": "91%", "Currency": "INR", "Status": "Attention", "Exceptions": "3 Unit Normalization Flags"},
        {"Supplier": "BoxCraft Ltd", "File Format": "PDF (.pdf)", "Items Extracted": "27 / 30", "Confidence": "94%", "Currency": "INR", "Status": "Incomplete", "Exceptions": "3 Line Items Missing"},
        {"Supplier": "CorruSeal Global", "File Format": "Excel (.xlsx)", "Items Extracted": "30 / 30", "Confidence": "96%", "Currency": "USD", "Status": "Attention", "Exceptions": "Currency USD (Auto-converted)"},
        {"Supplier": "National Paper Mills", "File Format": "Scanned PNG", "Items Extracted": "30 / 30", "Confidence": "82%", "Currency": "INR", "Status": "Attention", "Exceptions": "Low-confidence OCR Extractions"}
    ]
    st.dataframe(pd.DataFrame(supplier_inbox), use_container_width=True, hide_index=True)
    
    st.divider()
    st.markdown("### Side-by-Side Extraction Review & Verification")
    
    col_src, col_ext = st.columns([1, 1])
    with col_src:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Original Source Document Snippet** (BoxCraft Ltd Quote.pdf)")
        st.code("""
        ====================================================
        BOXCRAFT LTD - COMMERCIAL QUOTATION
        Quote Ref: BC-2026-PKG
        
        Items 1 to 27: Quoted per technical specifications.
        Items 28, 29, 30: Currently out of stock. Omitting quote.
        Payment Terms: Net 30 Days | Delivery: Ex-Works
        ====================================================
        """, language="text")
        st.caption("Traceability: BoxCraft Quote.pdf — Page 1, Paragraph 3")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_ext:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Human-Readable AI Extraction Review** <span class='tag-ai-extracted'>Extracted</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Extraction Confidence:** 94% overall
        * **Extracted Items:** 27 out of 30 line items parsed successfully
        * **Items Requiring Review:** `ITEM-028`, `ITEM-029`, `ITEM-030` (Missing from quote)
        * **Commercial Exception:** Quoted Net 30 Days (RFx Target: Net 60 Days)
        * **Delivery Exception:** Ex-Works (RFx Target: Supplier Prepaid)
        """)
        if st.button("Confirm Extraction & Flag Exceptions"):
            st.success("Verification saved.")
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STAGE 3: COMPARE BIDS
# -----------------------------------------------------------------------------
elif stage == "Compare Bids":
    st.subheader("Supplier Bid Comparison Workspace")
    st.caption("Side-by-side evaluation across pricing, compliance, quality, and commercial terms.")
    
    # Filter Controls
    f_col1, f_col2 = st.columns([3, 1])
    with f_col1:
        comp_view = st.radio("Evaluation View:", ["Pricing Matrix", "Compliance & Quality", "Commercial Terms", "All Details"], horizontal=True)
    with f_col2:
        supplier_filter = st.selectbox("Supplier Filter:", ["All Suppliers", "Qualified Suppliers Only", "Exceptions Only"])

    st.write("")
    
    if comp_view in ["Pricing Matrix", "All Details"]:
        st.markdown("**Commercial Line Item Pricing Grid (Click any cell to edit):**")
        raw_matrix = get_vendor_mock_matrix()
        
        # Apply filtering if requested
        if supplier_filter == "Qualified Suppliers Only":
            raw_matrix = raw_matrix.drop(columns=["PackTech Solutions (INR)", "BoxCraft Ltd (INR)"])
            
        edited_matrix = st.data_editor(
            raw_matrix,
            use_container_width=True,
            height=380,
            hide_index=True
        )
        
    if comp_view in ["Compliance & Quality", "Commercial Terms", "All Details"]:
        st.write("")
        st.markdown("**Qualitative & Compliance Matrix:**")
        q_matrix = get_questionnaire_matrix()
        st.dataframe(q_matrix, use_container_width=True, hide_index=True)
        
    st.divider()
    st.markdown("### Why is this flagged?")
    
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("<span class='badge-amber'>Missing Lines Flag</span> **BoxCraft Ltd**", unsafe_allow_html=True)
        st.markdown("""
        * **Requirement:** 30 Line Items
        * **Quoted:** 27 Line Items
        * **Explanation:** Supplier omitted items 28-30. Awarding 100% volume to BoxCraft creates a 3-item supply gap.
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with e2:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("<span class='badge-amber'>Currency Flag</span> **CorruSeal Global**", unsafe_allow_html=True)
        st.markdown("""
        * **Requirement:** Quoted in INR
        * **Quoted:** Quoted in USD ($0.23/unit)
        * **Explanation:** System normalized pricing at 83.5 exchange rate. Unhedged foreign exchange risk exists.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with e3:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("<span class='badge-red'>Quality Flag</span> **PackTech Solutions**", unsafe_allow_html=True)
        st.markdown("""
        * **Requirement:** ISO 9001 Certified
        * **Quoted:** No Certification
        * **Explanation:** Supplier failed mandatory quality requirements. Defect rate (2.1%) exceeds 0.5% limit.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STAGE 4: ANALYZE & DECIDE
# -----------------------------------------------------------------------------
elif stage == "Analyze & Decide":
    st.subheader("Analyze your sourcing options")
    st.caption("Ask natural-language questions and compare sourcing scenarios before making an award decision.")
    
    # Calculate deterministic baseline spend metrics
    raw_matrix = get_vendor_mock_matrix()
    calc = calculate_split_award_metrics(raw_matrix)
    
    # Deterministic Sourcing Metrics
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Lowest Single Supplier", f"₹{calc['best_single_spend']:,.0f}", f"{calc['best_single_supplier']}")
    k2.metric("Split-Award Total Spend", f"₹{calc['split_spend']:,.0f}", f"-₹{calc['savings']:,.0f}")
    k3.metric("Calculated Split Savings", f"{calc['savings_pct']}%", "vs Single Supplier")
    k4.metric("Qualified Suppliers", "3 of 5", "2 Disqualified / Incomplete")
    
    st.divider()
    
    # Suggested Questions Prompt Bar
    st.markdown("**Suggested Sourcing Questions:**")
    q_col1, q_col2, q_col3 = st.columns(3)
    
    prompt_choice = None
    if q_col1.button("💡 What would we save with a split award?"):
        prompt_choice = f"Compare single-vendor scenarios vs split-award options. The pre-calculated lowest split spend is ₹{calc['split_spend']:,.0f} and lowest single vendor is ₹{calc['best_single_spend']:,.0f}. Provide advantages and trade-offs."
    if q_col2.button("⚠️ Which suppliers have missing requirements?"):
        prompt_choice = "Which suppliers failed mandatory quality checks or missed line items, and what risks should I consider before awarding?"
    if q_col3.button("📊 Compare lowest-cost qualified suppliers"):
        prompt_choice = "Compare the trade-offs between Apex Packaging and CorruSeal Global regarding pricing, quality, payment terms, and currency exposure."

    user_query = st.text_input("Ask a question across all supplier responses:", value=prompt_choice if prompt_choice else "", placeholder="e.g. Compare the trade-offs between Apex Packaging and CorruSeal Global...")
    
    if user_query:
        with st.spinner("Analyzing dataset with Gemini 2.5 Flash..."):
            matrix_json = raw_matrix.to_json(orient="records")
            q_json = get_questionnaire_matrix().to_json(orient="records")
            
            system_instruction = f"""
            You are a procurement decision support assistant.
            Analyze the supplier response dataset and answer the user query in a structured format.
            Do NOT state that the AI is making the decision. Frame as scenario comparison.
            
            Structure your response into the following clear markdown sections:
            1. **Answer & Scenario Summary**
            2. **Evidence & Pre-Calculated Data** (Best single: {calc['best_single_supplier']} @ ₹{calc['best_single_spend']:,.0f}, Split spend: ₹{calc['split_spend']:,.0f}, Savings: ₹{calc['savings']:,.0f})
            3. **Trade-offs & Advantages**
            4. **Exceptions & Operational Risks**
            5. **Data Sources & Traceability**
            
            Use clean markdown, bold metrics, and concise bullet points.
            """
            
            prompt = f"Commercial Pricing Dataset:\n{matrix_json}\n\nQuality Matrix:\n{q_json}\n\nUser Question: {user_query}"
            
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                
                st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
                st.markdown("### AI Scenario & Decision Analysis")
                st.write(response.text)
                st.markdown("</div>", unsafe_allow_html=True)
                
                st.write("")
                st.markdown("### Total Quoted Spend Comparison (INR)")
                
                summary_data = pd.DataFrame({
                    "Supplier": ["Apex Packaging", "PackTech (Failed Quality)", "BoxCraft (Incomplete)", "CorruSeal (USD->INR)", "National Paper Mills"],
                    "Total Spend (INR)": [1050000, 1120000, 890000, 1020000, 980000]
                })
                fig = px.bar(
                    summary_data, 
                    x="Supplier", 
                    y="Total Spend (INR)", 
                    color="Supplier",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    template="plotly_white",
                    title="Commercial Spend Profile Across All 5 Submissions"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Export Decision Summary
                csv = raw_matrix.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Decision Note & Matrix (CSV)",
                    data=csv,
                    file_name="RFQ_Procurement_Decision_Summary.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"Error querying AI engine: {e}")
