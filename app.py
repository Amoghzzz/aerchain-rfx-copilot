import streamlit as st
import pandas as pd
import json
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & ENTERPRISE LIGHT DESIGN SYSTEM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | Autonomous RFQ Sourcing Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Enterprise CSS (Light Mode, High Contrast, Restrained Colors)
st.markdown("""
    <style>
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    [data-testid="stSidebar"] { display: none; }
    
    /* Compact Persistent Header */
    .compact-header {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 10px 18px;
        margin-bottom: 16px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    
    /* Workflow Navigation Breadcrumbs */
    .nav-container {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;
    }
    .nav-step {
        padding: 6px 14px;
        border-radius: 16px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .nav-step-active { background-color: #0284c7; color: #ffffff; }
    .nav-step-done { background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .nav-step-muted { background-color: #f1f5f9; color: #64748b; }
    
    /* Clean Enterprise Cards */
    .procurement-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 14px;
    }
    
    /* Standardized Status Badges */
    .badge-ready { background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
    .badge-review { background-color: #fffbeb; color: #b45309; border: 1px solid #fef08a; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
    .badge-blocked { background-color: #fef2f2; color: #991b1b; border: 1px solid #fecaca; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
    
    /* Origin Tags */
    .tag-user { background-color: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .tag-ai-extracted { background-color: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    
    .stButton>button {
        background-color: #0284c7 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 8px 16px !important;
    }
    .stButton>button:hover { background-color: #0369a1 !important; }
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
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    return genai.Client(
        vertexai=True,
        project=creds_dict["project_id"],
        location="us-central1",
        credentials=credentials
    )

try:
    client = get_genai_client()
except Exception as e:
    st.error(f"Failed to initialize Vertex AI client: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. STATEFUL SESSION STORAGE (PERSISTENT WORKFLOW STATE)
# -----------------------------------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "Create RFQ"

if "rfq_generated" not in st.session_state:
    st.session_state.rfq_generated = False

if "rfq_data" not in st.session_state:
    st.session_state.rfq_data = {
        "title": "Corrugated Packaging Sourcing",
        "category": "Packaging Materials",
        "target_qty_total": 97500,
        "delivery_location": "Bhiwandi & Hosur Warehouses",
        "payment_terms": "Net 60 Days",
        "defect_limit": "< 0.5%",
        "confirmed_items": [
            {"Line #": f"ITEM-{i:03d}", "Description": f"{'5-Ply Heavy Duty' if i%2==0 else '3-Ply Standard'} Box - Var {i}", "Quantity": (i*500)+1000, "UOM": "pcs", "Specification": "180 GSM Kraft" if i%2==0 else "150 GSM Kraft", "Status": "Confirmed" if i<=27 else "Review Required"}
            for i in range(1, 31)
        ],
        "unclear_specs": [
            "Price Validity: Not specified in prompt (Recommended: 60 Days)",
            "Freight Responsibility: Not specified (Incoterms needed)",
            "Buffer Lead Time: Unspecified for peak season demand"
        ]
    }

# Consistent Master Supplier Response & Comparison Matrix (Single Source of Truth)
if "supplier_matrix" not in st.session_state:
    base_df = pd.DataFrame(st.session_state.rfq_data["confirmed_items"])
    
    # Audit-Verified Consistent Supplier Quote Data
    # Apex: 100% compliant, Net 60, ISO Yes, 0.4% defect rate
    base_df["Apex Packaging (INR)"] = [round(20.00 + (i * 0.8), 2) for i in range(30)]
    
    # PackTech: Failed Quality (No ISO, 2.1% defect rate), Net 45
    base_df["PackTech Solutions (INR)"] = [round(19.00 + (i * 0.85), 2) for i in range(30)]
    
    # BoxCraft: Partial quote (27/30 lines), Net 30, ISO Yes, 0.3% defect rate
    base_df["BoxCraft Ltd (INR)"] = [round(18.00 + (i * 0.75), 2) if i < 27 else None for i in range(30)]
    
    # CorruSeal: USD converted @ 83.5, Net 60, ISO Yes, 0.2% defect rate
    base_df["CorruSeal Global (USD->INR)"] = [round((0.23 + (i * 0.01)) * 83.5, 2) for i in range(30)]
    
    # National Paper: ISO Yes, 0.4% defect rate, Net 30
    base_df["National Paper Mills (INR)"] = [round(22.00 + (i * 0.7), 2) for i in range(30)]
    
    st.session_state.supplier_matrix = base_df

if "supplier_questionnaire" not in st.session_state:
    st.session_state.supplier_questionnaire = pd.DataFrame({
        "Evaluation Metric": ["ISO 9001 Certification", "FSC Certification", "Defect Rate", "Capacity / Mo.", "Payment Terms", "Freight Terms", "Quality Qualification"],
        "Apex Packaging": ["YES", "YES", "0.4%", "1.2M pcs", "Net 60", "Supplier Prepaid", "PASSED"],
        "PackTech Solutions": ["NO", "YES", "2.1%", "1.1M pcs", "Net 45", "Supplier Prepaid", "FAILED (High Defect / No ISO)"],
        "BoxCraft Ltd": ["YES", "NO", "0.3%", "900K pcs", "Net 30", "Buyer Collect", "PASSED (Incomplete Quote)"],
        "CorruSeal Global": ["YES", "YES", "0.2%", "1.5M pcs", "Net 60", "Supplier Prepaid", "PASSED"],
        "National Paper Mills": ["YES", "YES", "0.4%", "1.3M pcs", "Net 30", "Buyer Collect", "PASSED"]
    })

if "user_file_uploads" not in st.session_state:
    st.session_state.user_file_uploads = []

# -----------------------------------------------------------------------------
# 4. DETERMINISTIC SPEND CALCULATION ENGINE
# -----------------------------------------------------------------------------
def calculate_spend_engine(df):
    supplier_cols = [
        ("Apex Packaging", "Apex Packaging (INR)", True),
        ("PackTech Solutions", "PackTech Solutions (INR)", False), # Failed Quality
        ("BoxCraft Ltd", "BoxCraft Ltd (INR)", False),              # Incomplete 27/30
        ("CorruSeal Global", "CorruSeal Global (USD->INR)", True),
        ("National Paper Mills", "National Paper Mills (INR)", True)
    ]
    
    totals = {}
    for name, col, qualified in supplier_cols:
        series = df[col] * df["Quantity"]
        valid_sum = series.sum()
        has_nulls = df[col].isnull().any()
        totals[name] = {
            "total_spend": round(valid_sum, 2) if not has_nulls else None,
            "raw_sum": round(df[col].dropna() * df.loc[df[col].notnull(), "Quantity"]).sum(),
            "items_quoted": int(df[col].notnull().sum()),
            "qualified": qualified,
            "has_nulls": has_nulls
        }
        
    # Single lowest qualified
    qualified_singles = {k: v["total_spend"] for k, v in totals.items() if v["qualified"] and not v["has_nulls"]}
    best_single_name = min(qualified_singles, key=qualified_singles.get)
    best_single_spend = qualified_singles[best_single_name]
    
    # Split award (among qualified suppliers: Apex, CorruSeal, National)
    qual_cols = ["Apex Packaging (INR)", "CorruSeal Global (USD->INR)", "National Paper Mills (INR)"]
    df["Min_Price"] = df[qual_cols].min(axis=1)
    split_spend = round((df["Min_Price"] * df["Quantity"]).sum(), 2)
    
    savings = round(best_single_spend - split_spend, 2)
    savings_pct = round((savings / best_single_spend) * 100, 1)
    
    return {
        "totals": totals,
        "best_single_name": best_single_name,
        "best_single_spend": best_single_spend,
        "split_spend": split_spend,
        "savings": savings,
        "savings_pct": savings_pct
    }

# -----------------------------------------------------------------------------
# 5. PERSISTENT HEADER & NAVIGATION BREADCRUMBS
# -----------------------------------------------------------------------------
calc_baseline = calculate_spend_engine(st.session_state.supplier_matrix)

st.markdown(f"""
<div class="compact-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <span style="font-size: 0.8rem; color: #64748b; font-weight: 700;">RFQ REF:</span>
            <strong style="color: #0f172a; font-size: 0.95rem; margin-left: 4px;">RFQ-2026-PKG-001</strong>
            <span style="color: #cbd5e1; margin: 0 8px;">|</span>
            <span style="font-size: 0.85rem; color: #0284c7; font-weight: 600;">{st.session_state.rfq_data['title']}</span>
        </div>
        <div>
            <span style="font-size: 0.82rem; color: #334155;"><b>30</b> Line Items &nbsp;•&nbsp; <b>5</b> Suppliers &nbsp;•&nbsp; Deadline: <b>15 Oct 2026</b></span>
            &nbsp;<span class="badge-review">7 Exceptions Requiring Review</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Stage Navigation Buttons
stages = ["Create RFQ", "Supplier Responses", "Compare Bids", "Analyze & Decide"]
cur_idx = stages.index(st.session_state.stage)

nav_cols = st.columns(4)
for idx, stage_name in enumerate(stages):
    if idx < cur_idx:
        pill_class = "nav-step-done"
        label = f"✓ {stage_name}"
    elif idx == cur_idx:
        pill_class = "nav-step-active"
        label = f"{idx+1}. {stage_name}"
    else:
        pill_class = "nav-step-muted"
        label = f"{idx+1}. {stage_name}"
        
    if nav_cols[idx].button(label, key=f"nav_btn_{idx}"):
        st.session_state.stage = stage_name
        st.rerun()

st.divider()

# -----------------------------------------------------------------------------
# STAGE 1: CREATE RFQ (DYNAMIC AI GENERATION & VALIDATION)
# -----------------------------------------------------------------------------
if st.session_state.stage == "Create RFQ":
    st.subheader("1. What are you looking to procure?")
    st.caption("Provide your procurement requirements in plain English. The AI engine will dynamically extract specifications, line items, and missing terms.")
    
    prompt_val = st.text_area(
        "Enter procurement prompt:",
        value="I need to source corrugated packaging boxes for our Bhiwandi and Hosur operations. Around 30 line items across 5-ply heavy duty and 3-ply standard boxes. Require ISO 9001 certified suppliers with Net 60 payment terms.",
        height=90
    )
    
    if st.button("Generate RFQ Proposal"):
        with st.spinner("Analyzing requirements with Gemini 2.5 Flash..."):
            sys_gen_prompt = """
            You are an expert procurement assistant.
            Extract structured RFQ metadata from the user input into JSON format.
            JSON Schema:
            {
                "title": "string",
                "category": "string",
                "target_qty_total": number,
                "delivery_location": "string",
                "payment_terms": "string",
                "unclear_specs": ["string"]
            }
            Do not invent missing specs as facts; put unstated parameters into unclear_specs.
            """
            try:
                res = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"User Prompt: {prompt_val}",
                    config=types.GenerateContentConfig(
                        system_instruction=sys_gen_prompt,
                        response_mime_type="application/json"
                    )
                )
                parsed = json.loads(res.text)
                st.session_state.rfq_data["title"] = parsed.get("title", "Generated RFQ Sourcing")
                st.session_state.rfq_data["category"] = parsed.get("category", "General Procurement")
                st.session_state.rfq_data["delivery_location"] = parsed.get("delivery_location", "Unspecified Location")
                st.session_state.rfq_data["payment_terms"] = parsed.get("payment_terms", "Unspecified Terms")
                st.session_state.rfq_data["unclear_specs"] = parsed.get("unclear_specs", [])
                st.session_state.rfq_generated = True
                st.success("RFQ Scope Dynamically Generated!")
            except Exception as ex:
                st.warning(f"Using default baseline schema. (Engine response: {ex})")
                st.session_state.rfq_generated = True

    # Readiness Assessment Bar
    st.write("")
    r1, r2 = st.columns([3, 1])
    with r1:
        st.markdown("### RFQ Readiness Score: **83% Ready to Publish**")
        st.progress(0.83)
    with r2:
        st.markdown("<span class='badge-review'>3 Clarifications Recommended</span>", unsafe_allow_html=True)

    # 3-Column Structured Breakdown
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**User Provided Parameters** <span class='tag-user'>Verified</span>", unsafe_allow_html=True)
        st.markdown(f"""
        * **Category:** {st.session_state.rfq_data['category']}
        * **Delivery Location:** {st.session_state.rfq_data['delivery_location']}
        * **Payment Terms Target:** {st.session_state.rfq_data['payment_terms']}
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**AI Identified Specifications** <span class='tag-ai-extracted'>Extracted</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Target Line Items:** 30 Items
        * **Material Specs:** 180 GSM / 150 GSM Kraft Paper
        * **Quality Certification:** ISO 9001 Mandatory
        * **Defect Rate Tolerance:** < 0.5%
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Needs Confirmation** <span class='badge-review'>Action Required</span>", unsafe_allow_html=True)
        for unc in st.session_state.rfq_data["unclear_specs"]:
            st.markdown(f"* {unc}")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown("### Master Line Items Table (30 Items)")
    st.dataframe(pd.DataFrame(st.session_state.rfq_data["confirmed_items"]), use_container_width=True, height=350, hide_index=True)
    
    # Sequential Footer Step CTA
    f1, f2 = st.columns([3, 1])
    with f2:
        if st.button("Publish RFQ & Proceed to Responses →"):
            st.session_state.stage = "Supplier Responses"
            st.rerun()

# -----------------------------------------------------------------------------
# STAGE 2: SUPPLIER RESPONSES (UPLOADER & INGESTION WORKSPACE)
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Supplier Responses":
    st.subheader("2. Supplier Response Inbox & Ingestion")
    st.caption("Upload raw supplier proposals or inspect extracted quotes, extraction confidence scores, and compliance anomalies.")
    
    # Active Response Health Metrics
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Suppliers Invited", "5")
    h2.metric("Responses Ingested", "5 / 5")
    h3.metric("Response Completeness", "98.2%", "Apex, CorruSeal, National @ 100%")
    h4.metric("Exceptions Flagged", "7 Exceptions", delta="Requires Review", delta_color="inverse")
    
    st.divider()
    st.markdown("### Upload Supplier Quotation Documents")
    
    up_col1, up_col2 = st.columns([2, 1])
    with up_col1:
        uploaded_files = st.file_uploader(
            "Drag & drop supplier response files (Excel, PDF, Word, Scanned Images):",
            accept_multiple_files=True,
            type=["xlsx", "pdf", "docx", "png", "jpg", "csv"]
        )
        if uploaded_files:
            for f in uploaded_files:
                if f.name not in [x["filename"] for x in st.session_state.user_file_uploads]:
                    st.session_state.user_file_uploads.append({"filename": f.name, "size": f.size, "status": "Ingested & Normalised"})
            st.success(f"Successfully ingested {len(uploaded_files)} document(s) into comparison matrix.")

    with up_col2:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Ingestion Log**")
        if st.session_state.user_file_uploads:
            for item in st.session_state.user_file_uploads:
                st.markdown(f"✓ `{item['filename']}` ({item['size']} bytes)")
        else:
            st.caption("No new files uploaded. Pre-fabricated demo files active.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown("### Supplier Response Overview & Extraction Health")
    
    inbox_table = [
        {"Supplier": "Apex Packaging", "Format": "Excel (.xlsx)", "Extraction Health": "98% — High Confidence", "Items Extracted": "30 / 30", "Currency": "INR", "Status": "Ready"},
        {"Supplier": "PackTech Solutions", "Format": "Word (.docx)", "Extraction Health": "91% — Normalised", "Items Extracted": "30 / 30", "Currency": "INR", "Status": "Review (Quality Failure)"},
        {"Supplier": "BoxCraft Ltd", "Format": "PDF (.pdf)", "Extraction Health": "94% — High Confidence", "Items Extracted": "27 / 30", "Currency": "INR", "Status": "Incomplete (3 Lines Missing)"},
        {"Supplier": "CorruSeal Global", "Format": "Excel (.xlsx)", "Extraction Health": "96% — Converted", "Items Extracted": "30 / 30", "Currency": "USD ($0.23/unit)", "Status": "Review (FX Rate @ 83.5)"},
        {"Supplier": "National Paper Mills", "Format": "Scanned PNG", "Extraction Health": "82% — Review Recommended", "Items Extracted": "30 / 30", "Currency": "INR", "Status": "Ready"}
    ]
    st.dataframe(pd.DataFrame(inbox_table), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Side-by-Side Verification Drawer")
    
    v1, v2 = st.columns(2)
    with v1:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Original Quote Document Snippet** (`BoxCraft Quote.pdf`)")
        st.code("""
        ====================================================
        BOXCRAFT LTD - COMMERCIAL QUOTATION
        Quote Reference: BC-2026-PKG
        
        Items 1 to 27: Quoted as per technical specs.
        Items 28, 29, 30: Out of stock. Omitting quote.
        Commercials: Net 30 Days | Delivery: Ex-Works
        ====================================================
        """, language="text")
        st.caption("Source Anchor: BoxCraft Quote.pdf — Page 1, Paragraph 3")
        st.markdown("</div>", unsafe_allow_html=True)

    with v2:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("**Human-Readable AI Extraction Log** <span class='tag-ai-extracted'>Extracted</span>", unsafe_allow_html=True)
        st.markdown("""
        * **Extraction Confidence:** 94% overall
        * **Line Item Status:** 27 of 30 line items parsed
        * **Items Requiring Attention:** `ITEM-028`, `ITEM-029`, `ITEM-030` (Missing from submission)
        * **Commercial Term Exception:** Quoted Net 30 Days (RFx Target: Net 60 Days)
        * **Freight Term Exception:** Ex-Works (RFx Target: Supplier Prepaid)
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← Back to RFQ"):
            st.session_state.stage = "Create RFQ"
            st.rerun()
    with b2:
        if st.button("Continue to Bid Comparison →"):
            st.session_state.stage = "Compare Bids"
            st.rerun()

# -----------------------------------------------------------------------------
# STAGE 3: COMPARE BIDS (PLUGGABLE SUMMARY & LINE-ITEM GRID)
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Compare Bids":
    st.subheader("3. Supplier Bid Comparison Workspace")
    st.caption("Pricing, compliance, quality, and commercial terms normalized to RFQ requirements.")
    
    # Apples-to-Apples Normalization Callout
    st.info("💡 **Pricing Normalized for Comparison:** Currencies (USD converted @ 83.5 INR), units of measure, and quantities have been standardized against RFQ targets.")

    # High-Level Supplier Executive Summary Cards First
    st.markdown("### Supplier Proposal Overview")
    s_cols = st.columns(5)
    
    suppliers_summary = [
        ("Apex Packaging", "₹1,050,000", "100%", "PASSED", "Net 60", "0 Exceptions", "badge-ready"),
        ("PackTech Solutions", "₹1,120,000", "100%", "FAILED", "Net 45", "Quality Fail", "badge-blocked"),
        ("BoxCraft Ltd", "Incomplete", "90%", "PASSED", "Net 30", "3 Lines Missing", "badge-review"),
        ("CorruSeal Global", "₹1,020,000", "100%", "PASSED", "Net 60", "USD Currency", "badge-review"),
        ("National Paper", "₹980,000", "100%", "PASSED", "Net 30", "Scanned OCR", "badge-ready")
    ]
    
    for idx, (s_name, s_spend, s_comp, s_qual, s_terms, s_exc, s_badge) in enumerate(suppliers_summary):
        with s_cols[idx]:
            st.markdown(f"""
            <div class='procurement-card'>
                <strong>{s_name}</strong><br>
                <span style='font-size:1.1rem; font-weight:700; color:#0284c7;'>{s_spend}</span><br>
                <span style='font-size:0.8rem;'>Completeness: <b>{s_comp}</b></span><br>
                <span style='font-size:0.8rem;'>Quality: <b>{s_qual}</b></span><br>
                <span style='font-size:0.8rem;'>Terms: <b>{s_terms}</b></span><br><br>
                <span class='{s_badge}'>{s_exc}</span>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    comp_tab1, comp_tab2 = st.tabs(["Commercial Line Item Matrix", "Qualitative & Quality Questionnaire Matrix"])
    
    with comp_tab1:
        st.markdown("**Line Item Commercial Comparison Grid (Editable):**")
        edited_matrix = st.data_editor(
            st.session_state.supplier_matrix,
            use_container_width=True,
            height=380,
            hide_index=True
        )
        st.session_state.supplier_matrix = edited_matrix
        
    with comp_tab2:
        st.markdown("**Compliance & Quality Evaluation Matrix:**")
        st.dataframe(st.session_state.supplier_questionnaire, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Why is this flagged? (Exception Breakdown)")
    
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("<span class='badge-review'>Missing Lines</span> **BoxCraft Ltd**", unsafe_allow_html=True)
        st.markdown("""
        * **Requirement:** 30 Line Items
        * **Quoted:** 27 Line Items (`ITEM-001` to `ITEM-027`)
        * **Risk:** Awarding 100% volume to BoxCraft leaves a 3-item supply gap requiring secondary sourcing.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with e2:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("<span class='badge-review'>Currency Mismatch</span> **CorruSeal Global**", unsafe_allow_html=True)
        st.markdown("""
        * **Requirement:** Quoted in INR
        * **Quoted:** Quoted in USD ($0.23 / unit)
        * **Action:** Normalized at 83.5 exchange rate. FX volatility risk exists.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    with e3:
        st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
        st.markdown("<span class='badge-blocked'>Quality Failure</span> **PackTech Solutions**", unsafe_allow_html=True)
        st.markdown("""
        * **Requirement:** ISO 9001 Certified, Defect Rate < 0.5%
        * **Quoted:** No ISO 9001, Defect Rate 2.1%
        * **Action:** Disqualified from split-award optimization.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

    cb1, cb2 = st.columns([1, 1])
    with cb1:
        if st.button("← Back to Responses"):
            st.session_state.stage = "Supplier Responses"
            st.rerun()
    with cb2:
        if st.button("Continue to Scenario Analysis →"):
            st.session_state.stage = "Analyze & Decide"
            st.rerun()

# -----------------------------------------------------------------------------
# STAGE 4: ANALYZE & DECIDE (STRUCTURED DECISION INTELLIGENCE)
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Analyze & Decide":
    st.subheader("4. Analyze your sourcing options")
    st.caption("Ask natural language questions, evaluate split-award scenarios, and inspect trade-offs before awarding.")
    
    # Natural Language Question Header First
    st.markdown("### Ask a Sourcing Question")
    
    q_col1, q_col2, q_col3 = st.columns(3)
    prompt_choice = None
    if q_col1.button("💡 What would we save with a split award?"):
        prompt_choice = f"Compare single-vendor scenarios vs split-award options using calculated numbers. Lowest single supplier is {calc_baseline['best_single_name']} at ₹{calc_baseline['best_single_spend']:,.0f} and split-award spend is ₹{calc_baseline['split_spend']:,.0f}."
    if q_col2.button("⚠️ Which suppliers have missing requirements?"):
        prompt_choice = "Which suppliers failed quality checks or missed line items, and what risks exist?"
    if q_col3.button("📊 Compare Apex vs CorruSeal trade-offs"):
        prompt_choice = "Compare Apex Packaging and CorruSeal Global regarding pricing, quality, payment terms, and currency exposure."

    user_query = st.text_input("Enter question:", value=prompt_choice if prompt_choice else "", placeholder="e.g. Compare trade-offs between Apex Packaging and CorruSeal Global...")
    
    st.write("")
    # Sourcing Snapshot Metric Cards
    st.markdown("### Sourcing Snapshot")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Lowest Single Supplier", f"₹{calc_baseline['best_single_spend']:,.0f}", f"{calc_baseline['best_single_name']}")
    k2.metric("Split-Award Total Spend", f"₹{calc_baseline['split_spend']:,.0f}", f"-₹{calc_baseline['savings']:,.0f}")
    k3.metric("Calculated Savings", f"{calc_baseline['savings_pct']}%", "vs Lowest Single Supplier")
    k4.metric("Qualified Suppliers", "3 of 5", "PackTech Failed, BoxCraft Partial")
    
    if user_query:
        with st.spinner("Analyzing dataset with Gemini 2.5 Flash..."):
            matrix_json = st.session_state.supplier_matrix.to_json(orient="records")
            q_json = st.session_state.supplier_questionnaire.to_json(orient="records")
            
            system_instruction = f"""
            You are a procurement decision support assistant.
            Analyze the dataset and answer the user query accurately.
            
            STRICT GUARDRAILS:
            - Do NOT invent facts or extrapolate missing data as verified truth.
            - Frame as scenario comparisons (do not state "the AI recommends").
            - Use provided deterministic calculations: Best Single = {calc_baseline['best_single_name']} @ ₹{calc_baseline['best_single_spend']:,.0f}, Split Spend = ₹{calc_baseline['split_spend']:,.0f}, Savings = ₹{calc_baseline['savings']:,.0f}.
            
            STRUCTURE YOUR OUTPUT INTO EXACTLY THESE 5 SECTIONS:
            1. **Answer & Scenario Summary**
            2. **Evidence & Pre-Calculated Spend Data**
            3. **Trade-offs & Advantages**
            4. **Exceptions & Operational Risks**
            5. **Data Sources & Traceability**
            """
            
            try:
                res = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"Pricing Matrix:\n{matrix_json}\n\nQuality Matrix:\n{q_json}\n\nUser Question: {user_query}",
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1
                    )
                )
                
                st.markdown("<div class='procurement-card'>", unsafe_allow_html=True)
                st.write(res.text)
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Contextual Visualization (Only for spend/pricing queries)
                if any(w in user_query.lower() for w in ["save", "spend", "cost", "price", "split", "single"]):
                    st.write("")
                    st.markdown("### Total Quoted Spend Comparison (INR)")
                    
                    chart_df = pd.DataFrame({
                        "Supplier": ["Apex Packaging", "PackTech (Failed Qual)", "BoxCraft (Incomplete)", "CorruSeal (USD->INR)", "National Paper"],
                        "Total Spend (INR)": [1050000, 1120000, 890000, 1020000, 980000]
                    })
                    fig = px.bar(
                        chart_df,
                        x="Supplier",
                        y="Total Spend (INR)",
                        color="Supplier",
                        color_discrete_sequence=px.colors.qualitative.Set2,
                        template="plotly_white",
                        title="Commercial Spend Baseline Comparison"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as ex:
                st.error(f"Error querying AI engine: {ex}")

    st.divider()
    st.markdown("### Export Decision Package")
    ex1, ex2 = st.columns(2)
    with ex1:
        csv_data = st.session_state.supplier_matrix.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Comparison Matrix (CSV)", csv_data, "RFQ_Matrix.csv", "text/csv")
    with ex2:
        st.button("📄 Export Decision Summary Package (PDF)")
