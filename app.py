import streamlit as st
import pandas as pd
import json
import re
import io
import plotly.express as px
from google import genai
from google.oauth2 import service_account
from google.genai import types

# Native document parsing libraries with graceful stream fallbacks
try:
    import fitz  # PyMuPDF for PDF
except ImportError:
    fitz = None

try:
    import openpyxl  # OpenPyXL for XLSX
except ImportError:
    openpyxl = None

try:
    import docx  # python-docx for DOCX
except ImportError:
    docx = None

# -----------------------------------------------------------------------------
# 1. CENTRALIZED CONSTANTS & SUPPLIER SCHEMA
# -----------------------------------------------------------------------------
DEMO_FX_RATE = 83.50  # USD to INR Demo FX Normalization Rate

SUPPLIERS = [
    "Apex Packaging",
    "BoxCraft Ltd",
    "CorruSeal Global",
    "National Paper Mills",
    "PackTech Solutions"
]

SUPPLIER_MAP = {
    "Apex Packaging": {"prefix": "Apex", "orig_col": "Apex_Orig_Price", "norm_col": "Apex_Norm_INR", "status_col": "Apex_Status", "conf_col": "Apex_Confidence"},
    "BoxCraft Ltd": {"prefix": "BoxCraft", "orig_col": "BoxCraft_Orig_Price", "norm_col": "BoxCraft_Norm_INR", "status_col": "BoxCraft_Status", "conf_col": "BoxCraft_Confidence"},
    "CorruSeal Global": {"prefix": "CorruSeal", "orig_col": "CorruSeal_Orig_Price", "norm_col": "CorruSeal_Norm_INR", "status_col": "CorruSeal_Status", "conf_col": "CorruSeal_Confidence"},
    "National Paper Mills": {"prefix": "National", "orig_col": "National_Orig_Price", "norm_col": "National_Norm_INR", "status_col": "National_Status", "conf_col": "National_Confidence"},
    "PackTech Solutions": {"prefix": "PackTech", "orig_col": "PackTech_Orig_Price", "norm_col": "PackTech_Norm_INR", "status_col": "PackTech_Status", "conf_col": "PackTech_Confidence"}
}

# -----------------------------------------------------------------------------
# 2. PAGE CONFIGURATION & ENTERPRISE SaaS STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | Procurement Intelligence Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Quiet Design System - Flat & Spacing-First Architecture
st.markdown("""
    <style>
    /* Base Setup & Background */
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    [data-testid="stSidebar"] { display: none; }
    
    /* Header Container - Flat Integration */
    .flat-header {
        background-color: #FFFFFF;
        border-bottom: 1px solid #E2E8F0;
        padding: 20px 32px 16px 32px;
        margin-bottom: 0px;
    }
    
    .section-spacing {
        height: 16px;
    }
    
    /* Workspace Sections */
    .workspace-section {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 24px;
        margin-bottom: 20px;
    }

    /* Structured Output Metric Cards */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 16px;
        text-align: center;
    }
    .metric-card-val {
        font-size: 1.35rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-card-lbl {
        font-size: 0.75rem;
        font-weight: 500;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }
    
    /* Status Badges */
    .badge-confirmed { background-color: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-normalized { background-color: #F0F9FF; color: #0369A1; border: 1px solid #BAE6FD; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-review { background-color: #FFFBEB; color: #B45309; border: 1px solid #FEF08A; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-missing { background-color: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-status { background-color: #F1F5F9; color: #334155; border: 1px solid #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }

    /* Button Hierarchy Overrides */
    .stButton button[kind="primary"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        border: 1px solid #2563EB !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
    }
    .stButton button[kind="primary"]:hover {
        background-color: #1D4ED8 !important;
    }
    .stButton button[kind="secondary"] {
        background-color: #FFFFFF !important;
        color: #334155 !important;
        border: 1px solid #CBD5E1 !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
    }
    .stButton button[kind="secondary"]:hover {
        background-color: #F1F5F9 !important;
    }
    
    /* Horizontal Stepper Bar Container */
    .stepper-flat-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background-color: #FFFFFF;
        border-bottom: 1px solid #E2E8F0;
        padding: 12px 32px;
        margin-bottom: 24px;
    }
    </style>
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
    st.error("We couldn't connect to the procurement AI service. Please verify system credentials.")
    st.stop()

def extract_json_from_response(text):
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r'```(?:json)?\s*(\{.*\}|\[.*\])\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError("Could not parse valid JSON from AI response.")

# -----------------------------------------------------------------------------
# 4. UNTRUNCATED NATIVE DOCUMENT EXTRACTION HELPERS
# -----------------------------------------------------------------------------
def parse_raw_document_content(file_bytes, filename, mime_type):
    extracted_text = ""
    
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num, page in enumerate(doc, start=1):
                extracted_text += f"\n--- Page {page_num} ---\n" + page.get_text("text")
        else:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
            
    elif mime_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"] or filename.lower().endswith(".xlsx"):
        if openpyxl:
            wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                extracted_text += f"\n--- Sheet: {sheetname} ---\n"
                for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                    row_vals = [str(cell) for cell in row if cell is not None]
                    if row_vals:
                        extracted_text += f"Row {row_idx}: " + " | ".join(row_vals) + "\n"
        else:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")

    elif filename.lower().endswith(".docx"):
        if docx:
            doc = docx.Document(io.BytesIO(file_bytes))
            for p in doc.paragraphs:
                if p.text.strip():
                    extracted_text += p.text + "\n"
            for table in doc.tables:
                for row in table.rows:
                    extracted_text += " | ".join([cell.text.strip() for cell in row.cells]) + "\n"
        else:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")

    else:
        extracted_text = file_bytes.decode("utf-8", errors="ignore")
        
    return extracted_text if extracted_text.strip() else file_bytes.decode("utf-8", errors="ignore")

# -----------------------------------------------------------------------------
# 5. CANONICAL DATASETS & INITIAL ARCHETYPES
# -----------------------------------------------------------------------------
def get_canonical_30_items():
    specs = [
        ("Regular Slotted Carton", "5-ply, 18x12x10\", 180 GSM Kraft", 4000, "pcs", "Bhiwandi Warehouse"),
        ("Regular Slotted Carton", "5-ply, 20x14x12\", 180 GSM Kraft", 3500, "pcs", "Bhiwandi Warehouse"),
        ("Regular Slotted Carton", "3-ply, 12x10x8\", 150 GSM Kraft", 5000, "pcs", "Bhiwandi Warehouse"),
        ("Regular Slotted Carton", "3-ply, 14x10x6\", 150 GSM Kraft", 4500, "pcs", "Bhiwandi Warehouse"),
        ("Heavy Duty Shipping Master Box", "5-ply, 24x18x18\", 200 GSM Kraft", 2500, "pcs", "Hosur Facility"),
        ("Heavy Duty Shipping Master Box", "5-ply, 28x20x20\", 200 GSM Kraft", 2000, "pcs", "Hosur Facility"),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 10x8x4\", 150 GSM White Kraft", 6000, "pcs", "Bhiwandi Warehouse"),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 12x9x4\", 150 GSM White Kraft", 5500, "pcs", "Bhiwandi Warehouse"),
        ("Corrugated Partition Tray", "3-ply, 12-Grid Insert, 18x12\", 120 GSM", 8000, "pcs", "Hosur Facility"),
        ("Corrugated Partition Tray", "3-ply, 24-Grid Insert, 20x14\", 120 GSM", 7500, "pcs", "Hosur Facility"),
        ("Die-Cut Self-Locking Box", "3-ply, B-Flute, 8x6x4\", 150 GSM", 6500, "pcs", "Bhiwandi Warehouse"),
        ("Die-Cut Self-Locking Box", "3-ply, B-Flute, 12x8x5\", 150 GSM", 6000, "pcs", "Bhiwandi Warehouse"),
        ("Telescopic Top/Bottom Box", "5-ply, 16x16x12\", 180 GSM Kraft", 3000, "pcs", "Hosur Facility"),
        ("Telescopic Top/Bottom Box", "5-ply, 20x20x15\", 180 GSM Kraft", 2800, "pcs", "Hosur Facility"),
        ("Heavy Duty Pallet Outer Box", "7-ply, Heavy Outer, 40x48x30\", 250 GSM", 800, "pcs", "Hosur Facility"),
        ("Regular Slotted Carton", "5-ply, 15x10x10\", 180 GSM Kraft", 4200, "pcs", "Bhiwandi Warehouse"),
        ("Regular Slotted Carton", "3-ply, 10x8x6\", 150 GSM Kraft", 7000, "pcs", "Bhiwandi Warehouse"),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 8x5x3\", 150 GSM White", 9000, "pcs", "Bhiwandi Warehouse"),
        ("Corrugated Layer Pad", "3-ply Corrugated Sheet, 18x12\", 150 GSM", 12000, "pcs", "Hosur Facility"),
        ("Corrugated Layer Pad", "5-ply Corrugated Sheet, 20x14\", 180 GSM", 10000, "pcs", "Hosur Facility"),
        ("Regular Slotted Carton", "5-ply, 22x16x14\", 180 GSM Kraft", 3200, "pcs", "Bhiwandi Warehouse"),
        ("Heavy Duty Shipping Master Box", "5-ply, 30x22x22\", 200 GSM Kraft", 1500, "pcs", "Hosur Facility"),
        ("Die-Cut Folder Box", "3-ply, C-Flute, 14x11x3\", 150 GSM", 5000, "pcs", "Bhiwandi Warehouse"),
        ("Corrugated Edge Protector", "L-Shape Heavy Corner Guard, 50x50x1000mm", 15000, "pcs", "Hosur Facility"),
        ("Regular Slotted Carton", "3-ply, 16x12x8\", 150 GSM Kraft", 5500, "pcs", "Bhiwandi Warehouse"),
        ("Heavy Duty Shipping Master Box", "5-ply, 25x15x15\", 180 GSM Kraft", 2200, "pcs", "Hosur Facility"),
        ("Corrugated Partition Tray", "3-ply, 6-Grid Insert, 15x10\", 120 GSM", 8500, "pcs", "Hosur Facility"),
        ("Regular Slotted Carton", "5-ply, 19x13x11\", 180 GSM Kraft", 3800, "pcs", "Bhiwandi Warehouse"),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 14x10x5\", 150 GSM White", 4800, "pcs", "Bhiwandi Warehouse"),
        ("Heavy Duty Pallet Outer Box", "7-ply Heavy Outer, 42x42x36\", 250 GSM", 600, "pcs", "Hosur Facility")
    ]
    
    items = []
    for idx, (title, spec, qty, uom, loc) in enumerate(specs, start=1):
        items.append({
            "Line #": f"ITEM-{idx:03d}",
            "Description": title,
            "Quantity": qty,
            "UOM": uom,
            "Specification": spec,
            "Delivery Location": loc,
            "Provenance": "User provided" if idx % 2 != 0 else "✦ AI suggested"
        })
    return items

def get_supplier_prefabricated_dataset():
    items = get_canonical_30_items()
    master = []
    
    for idx, it in enumerate(items, start=1):
        base_price = round(22.0 + (idx * 0.85) + ((idx % 3) * 1.5), 2)
        
        p1_orig = base_price
        p2_orig = round(base_price * 0.92, 2) if idx <= 27 else None
        p3_usd = round(0.24 + (idx * 0.0105), 2)
        p3_norm = round(p3_usd * DEMO_FX_RATE, 2)
        p4_per_100 = round(base_price * 96.0, 2)
        p4_norm = round(p4_per_100 / 100.0, 2)
        p5_orig = round(base_price * 0.95, 2) if idx <= 24 else None
        
        master.append({
            "Line #": it["Line #"],
            "Description": it["Description"],
            "Specification": it["Specification"],
            "Quantity": it["Quantity"],
            "UOM": it["UOM"],
            "Delivery Location": it["Delivery Location"],
            
            "Apex_Orig_Price": f"₹{p1_orig:.2f} / pc",
            "Apex_Norm_INR": p1_orig,
            "Apex_Status": "CONFIRMED",
            "Apex_Confidence": "98%",
            
            "BoxCraft_Orig_Price": f"₹{p2_orig:.2f} / pc" if p2_orig else "NOT QUOTED",
            "BoxCraft_Norm_INR": p2_orig,
            "BoxCraft_Status": "CONFIRMED" if p2_orig else "MISSING",
            "BoxCraft_Confidence": "95%" if p2_orig else "0%",
            
            "CorruSeal_Orig_Price": f"${p3_usd:.2f} / pc",
            "CorruSeal_Norm_INR": p3_norm,
            "CorruSeal_Status": "NORMALIZED",
            "CorruSeal_Confidence": "96%",
            
            "National_Orig_Price": f"₹{p4_per_100:.2f} / 100 pcs",
            "National_Norm_INR": p4_norm,
            "National_Status": "NORMALIZED" if idx != 20 else "REVIEW REQUIRED",
            "National_Confidence": "88%" if idx != 20 else "58% (Scanned Digit Ambiguity)",
            
            "PackTech_Orig_Price": f"₹{p5_orig:.2f} / pc" if p5_orig else "UNAVAILABLE (Prior-year reference without price)",
            "PackTech_Norm_INR": p5_orig,
            "PackTech_Status": "CONFIRMED" if p5_orig else "MISSING",
            "PackTech_Confidence": "90%" if p5_orig else "0%"
        })
    return pd.DataFrame(master)

def get_questionnaire_master_dataset():
    data = {
        "Questionnaire Metric": [
            "ISO 9001 Certification Attached?",
            "FSC Certification Attached?",
            "3-Year Verified Defect Rate",
            "Monthly Packaging Capacity",
            "Offered Payment Terms",
            "Freight Responsibility",
            "GST Registration Verified?",
            "Manufacturing Location"
        ],
        "Apex Packaging": ["YES", "YES", "0.4%", "1.2M pcs", "Net 60", "Supplier Prepaid (DDP)", "YES", "Bhiwandi, MH"],
        "BoxCraft Ltd": ["YES", "NO", "0.3%", "900K pcs", "Net 30", "Buyer Collect", "YES", "Pune, MH"],
        "CorruSeal Global": ["YES", "YES", "0.2%", "1.5M pcs", "Net 60", "Supplier Prepaid (DDP)", "YES", "Chennai, TN"],
        "National Paper Mills": ["YES", "YES", "0.4%", "1.3M pcs", "Net 30", "Buyer Collect", "YES", "Hosur, TN"],
        "PackTech Solutions": ["NO (Failed)", "YES", "2.1% (Exceeds 0.5%)", "1.1M pcs", "Net 45", "Supplier Prepaid (DDP)", "YES", "Bengaluru, KA"]
    }
    return pd.DataFrame(data)

# -----------------------------------------------------------------------------
# 6. PERSISTENT WORKFLOW STATE
# -----------------------------------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "Create RFQ"

if "rfq_status" not in st.session_state:
    st.session_state.rfq_status = "Draft"

if "rfq_generated" not in st.session_state:
    st.session_state.rfq_generated = False

if "responses_unlocked" not in st.session_state:
    st.session_state.responses_unlocked = False

if "compare_unlocked" not in st.session_state:
    st.session_state.compare_unlocked = False

if "analyze_unlocked" not in st.session_state:
    st.session_state.analyze_unlocked = False

if "uploaded_suppliers" not in st.session_state:
    st.session_state.uploaded_suppliers = set()

if "rfq_data" not in st.session_state:
    st.session_state.rfq_data = {
        "title": "Corrugated Packaging Sourcing 2026",
        "category": "Packaging Materials",
        "scope": "Procurement of 30 corrugated box SKUs for Western and Southern logistics hubs.",
        "delivery_locations": "Bhiwandi Warehouse & Hosur Facility",
        "response_deadline": "15 Oct 2026",
        "payment_terms": "Net 60 Days",
        "price_validity": "60 Days Mandatory",
        "freight_terms": "Supplier Prepaid (DDP)",
        "iso_mandatory": True,
        "fsc_mandatory": False,
        "defect_limit": "< 0.5%",
        "line_items": get_canonical_30_items(),
        "unclear_specs": [
            "Price Validity: Mandatory duration not explicitly specified in prompt (Recommended: 60 Days)",
            "Buffer Lead Time: Volume spike buffer lead time not specified for peak season"
        ]
    }

if "master_matrix" not in st.session_state:
    st.session_state.master_matrix = get_supplier_prefabricated_dataset()

if "questionnaire_matrix" not in st.session_state:
    st.session_state.questionnaire_matrix = get_questionnaire_master_dataset()

if "uploaded_docs_log" not in st.session_state:
    st.session_state.uploaded_docs_log = []

if "pending_extraction" not in st.session_state:
    st.session_state.pending_extraction = None

if "exception_filter" not in st.session_state:
    st.session_state.exception_filter = "All line items"

# -----------------------------------------------------------------------------
# 7. DYNAMIC RULE-BASED QUALIFICATION & SPEND ENGINE
# -----------------------------------------------------------------------------
def calculate_deterministic_spend_engine(df, quest_df):
    """
    Computes all supplier metrics, qualification, coverage gaps, and optimal spend
    dynamically directly from master_matrix and questionnaire_matrix.
    Categorizes issues strictly into Missing, Data Quality, and Qualification failures.
    """
    qualification_status = {}
    for sname in SUPPLIERS:
        if sname in quest_df.columns:
            iso_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "ISO 9001 Certification Attached?", sname].values
            defect_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "3-Year Verified Defect Rate", sname].values
            
            iso_val = iso_rows[0] if len(iso_rows) > 0 else "NO"
            defect_val = defect_rows[0] if len(defect_rows) > 0 else "2.5%"
            
            try:
                defect_num = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(defect_val))[0])
            except Exception:
                defect_num = 1.0
                
            is_qualified = ("YES" in str(iso_val).upper()) and (defect_num < 0.5)
            
            reasons = []
            if "YES" not in str(iso_val).upper():
                reasons.append("ISO 9001 certification missing")
            if defect_num >= 0.5:
                reasons.append(f"Defect rate ({defect_val}) exceeds 0.5% threshold")
                
            qualification_status[sname] = {
                "qualified": is_qualified,
                "iso": iso_val,
                "defect": defect_val,
                "reason": "Qualified" if is_qualified else "; ".join(reasons)
            }

    supplier_totals = {}
    missing_line_count = 0
    data_quality_count = 0
    exception_line_numbers = set()
    dynamic_issue_descriptions = []

    for sname in SUPPLIERS:
        meta = SUPPLIER_MAP[sname]
        norm_col = meta["norm_col"]
        status_col = meta["status_col"]
        
        if norm_col not in df.columns:
            continue
            
        valid_rows = df[df[norm_col].notnull()]
        lines_quoted = len(valid_rows)
        has_missing = lines_quoted < len(df)
        
        total_spend = (valid_rows[norm_col] * valid_rows["Quantity"]).sum()
        is_qual = qualification_status.get(sname, {}).get("qualified", True)
        
        # Dynamic issue detection & categorization
        unquoted_items = []
        review_items = []
        for idx, row in df.iterrows():
            st_val = str(row.get(status_col, "")).upper()
            if st_val == "MISSING":
                missing_line_count += 1
                exception_line_numbers.add(row["Line #"])
                unquoted_items.append(row["Line #"])
            elif st_val == "REVIEW REQUIRED":
                data_quality_count += 1
                exception_line_numbers.add(row["Line #"])
                review_items.append(row["Line #"])

        if unquoted_items:
            dynamic_issue_descriptions.append(f"**{sname}:** {len(unquoted_items)} lines missing ({unquoted_items[0]} to {unquoted_items[-1]}).")
        if review_items:
            dynamic_issue_descriptions.append(f"**{sname}:** {len(review_items)} line needs review ({', '.join(review_items)}).")

        supplier_totals[sname] = {
            "total_spend": round(total_spend, 2),
            "lines_quoted": lines_quoted,
            "total_lines": len(df),
            "is_complete": not has_missing,
            "qualified": is_qual,
            "col_name": norm_col,
            "status_col": status_col
        }

    # Dynamic qualification issues
    for sname, q_info in qualification_status.items():
        if not q_info["qualified"]:
            dynamic_issue_descriptions.append(f"**{sname}:** Qualification failed ({q_info['reason']}).")

    # Identify lowest qualified single supplier with complete coverage
    qualified_complete = {
        k: v["total_spend"] for k, v in supplier_totals.items() 
        if v["qualified"] and v["is_complete"]
    }
    
    if qualified_complete:
        best_single_name = min(qualified_complete, key=qualified_complete.get)
        best_single_spend = qualified_complete[best_single_name]
        has_complete_option = True
    else:
        best_single_name = "None Available"
        best_single_spend = 0.0
        has_complete_option = False

    # Calculate Price-Optimized Qualified Split Scenario
    qual_cols = {
        sname: v["col_name"] 
        for sname, v in supplier_totals.items() 
        if v["qualified"]
    }
    
    split_allocation = []
    split_total = 0.0
    unassigned_count = 0
    
    for idx, row in df.iterrows():
        prices = {}
        for sname, col in qual_cols.items():
            if col in df.columns and pd.notnull(row[col]):
                status = str(row.get(SUPPLIER_MAP[sname]["status_col"], "")).upper()
                if status != "REVIEW REQUIRED":
                    prices[sname] = row[col]

        if prices:
            cheapest_supplier = min(prices, key=prices.get)
            cheapest_unit_price = prices[cheapest_supplier]
            line_total = cheapest_unit_price * row["Quantity"]
        else:
            cheapest_supplier = "Unassigned"
            cheapest_unit_price = 0.0
            line_total = 0.0
            unassigned_count += 1
            
        split_total += line_total
        split_allocation.append({
            "Line #": row["Line #"],
            "Description": row["Description"],
            "Quantity": row["Quantity"],
            "Awarded Supplier": cheapest_supplier,
            "Unit Price (INR)": cheapest_unit_price,
            "Extended Spend (INR)": round(line_total, 2)
        })

    price_diff = round(best_single_spend - split_total, 2) if has_complete_option else 0.0
    price_diff_pct = round((price_diff / best_single_spend) * 100, 1) if has_complete_option and best_single_spend > 0 else 0.0

    total_qualified_suppliers = sum(1 for v in qualification_status.values() if v["qualified"])
    total_disqualified_suppliers = sum(1 for v in qualification_status.values() if not v["qualified"])

    return {
        "qualification_status": qualification_status,
        "supplier_totals": supplier_totals,
        "best_single_name": best_single_name,
        "best_single_spend": best_single_spend,
        "has_complete_option": has_complete_option,
        "split_spend": round(split_total, 2),
        "price_diff": price_diff,
        "price_diff_pct": price_diff_pct,
        "split_allocation": pd.DataFrame(split_allocation),
        "unassigned_count": unassigned_count,
        "missing_line_count": missing_line_count,
        "data_quality_count": data_quality_count,
        "total_line_exceptions": len(exception_line_numbers),
        "exception_line_numbers": sorted(list(exception_line_numbers)),
        "dynamic_issue_descriptions": dynamic_issue_descriptions,
        "total_qualified_suppliers": total_qualified_suppliers,
        "total_disqualified_suppliers": total_disqualified_suppliers
    }

# -----------------------------------------------------------------------------
# 8. FLAT INTEGRATED HEADER & SEQUENTIAL STEPPER
# -----------------------------------------------------------------------------
calc = calculate_deterministic_spend_engine(st.session_state.master_matrix, st.session_state.questionnaire_matrix)

# Flat Integrated Header
st.markdown(f"""
<div class="flat-header">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
        <div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <h2 style="margin: 0; font-size: 1.3rem; font-weight: 600; color: #0F172A;">{st.session_state.rfq_data['title']}</h2>
                <span class="badge-status">{st.session_state.rfq_status}</span>
            </div>
            <div style="font-size: 0.82rem; color: #475569; margin-top: 4px;">
                RFQ-2026-PKG-001 &nbsp;·&nbsp; {len(st.session_state.rfq_data['line_items'])} line items &nbsp;·&nbsp; {len(SUPPLIERS)} suppliers &nbsp;·&nbsp; Due {st.session_state.rfq_data['response_deadline']}
            </div>
        </div>
        <div>
            <span class="badge-review">{calc['total_line_exceptions']} lines affected</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Strict Sequential Workflow Progress Stepper
stages = [
    ("Create RFQ", "Requirements", True),
    ("Supplier Responses", "Responses", st.session_state.responses_unlocked),
    ("Compare Bids", "Compare", st.session_state.compare_unlocked),
    ("Analyze & Decide", "Analyze", st.session_state.analyze_unlocked)
]
cur_idx = [s[0] for s in stages].index(st.session_state.stage)

st.markdown("<div class='stepper-flat-container'>", unsafe_allow_html=True)
step_cols = st.columns(4)
for idx, (stage_key, stage_label, is_unlocked) in enumerate(stages):
    if idx < cur_idx:
        btn_label = f"✓ {idx+1}. {stage_label}"
        b_type = "secondary"
    elif idx == cur_idx:
        btn_label = f"● {idx+1}. {stage_label}"
        b_type = "primary"
    else:
        btn_label = f"{idx+1}. {stage_label}"
        b_type = "secondary"
        
    with step_cols[idx]:
        if st.button(btn_label, key=f"seq_step_{idx}", type=b_type, disabled=not is_unlocked):
            st.session_state.stage = stage_key
            st.rerun()
        if not is_unlocked:
            st.caption("Available in sequence")
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STAGE 1: CREATE RFQ
# -----------------------------------------------------------------------------
if st.session_state.stage == "Create RFQ":
    st.markdown("### Create RFQ")
    st.caption("What do you need to source? Describe the items, quantities, specifications, delivery locations and commercial requirements you know.")

    prompt_val = st.text_area(
        "Requirements prompt:",
        value="I need to source corrugated packaging boxes for our Bhiwandi and Hosur logistics operations. Require 30 line items across 5-ply heavy duty and 3-ply standard shipping cartons. ISO 9001 certification mandatory with Net 60 payment terms.",
        height=90,
        placeholder="Include quantities, specifications, delivery locations, timing and commercial terms if known..."
    )
    
    if st.button("Generate RFQ draft", type="primary"):
        with st.spinner("Building RFQ draft · Extracting requirements · Structuring line items..."):
            sys_gen_prompt = """
            You are an expert enterprise procurement assistant.
            Analyze the user prompt and generate a structured RFx JSON proposal.
            JSON Schema required:
            {
                "title": "string",
                "category": "string",
                "scope": "string",
                "delivery_locations": "string",
                "payment_terms": "string",
                "unclear_specs": ["string"],
                "line_items": [
                    {
                        "Line #": "ITEM-001",
                        "Description": "string",
                        "Quantity": 4000,
                        "UOM": "pcs",
                        "Specification": "string",
                        "Delivery Location": "string",
                        "Provenance": "✦ AI suggested"
                    }
                ]
            }
            Generate exactly 30 realistic corrugated packaging line items if requested.
            """
            try:
                res = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"User Prompt: {prompt_val}",
                    config=types.GenerateContentConfig(
                        system_instruction=sys_gen_prompt,
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )
                parsed = extract_json_from_response(res.text)
                
                st.session_state.rfq_data["title"] = parsed.get("title", "Corrugated Packaging Sourcing")
                st.session_state.rfq_data["category"] = parsed.get("category", "Packaging Materials")
                st.session_state.rfq_data["scope"] = parsed.get("scope", "Procurement of corrugated boxes.")
                st.session_state.rfq_data["delivery_locations"] = parsed.get("delivery_locations", "Bhiwandi & Hosur")
                st.session_state.rfq_data["payment_terms"] = parsed.get("payment_terms", "Net 60 Days")
                st.session_state.rfq_data["unclear_specs"] = parsed.get("unclear_specs", [])
                
                if "line_items" in parsed and len(parsed["line_items"]) == 30:
                    st.session_state.rfq_data["line_items"] = parsed["line_items"]
                
                st.session_state.rfq_generated = True
                st.session_state.rfq_status = "Draft ready"
                st.success("RFQ draft created successfully.")
            except Exception:
                st.warning("Using standard canonical RFQ draft baseline.")
                st.session_state.rfq_generated = True

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
    # Actionable "Needs your review" Banner directly above line items
    if st.session_state.rfq_data["unclear_specs"]:
        st.markdown("#### Needs Your Review")
        st.caption("2 items need confirmation. You can still publish and complete these later:")
        
        rev_c1, rev_c2 = st.columns(2)
        with rev_c1:
            st.warning("**Price validity duration** — Unspecified\n\n*Recommended:* 60 days mandatory")
        with rev_c2:
            st.warning("**Volume buffer lead time** — Unspecified\n\n*Required for:* Peak demand season planning")
        st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)

    st.markdown(f"#### Requirements · {len(st.session_state.rfq_data['line_items'])} line items")
    st.caption("Origin: User provided · ✦ AI suggested — verify before publishing")
    
    items_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
    
    edited_items = st.data_editor(
        items_df,
        use_container_width=True,
        height=380,
        hide_index=True,
        column_config={
            "Line #": st.column_config.TextColumn("Line #", disabled=True, width="medium"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Quantity": st.column_config.NumberColumn("Quantity", format="%d", width="medium"),
            "UOM": st.column_config.SelectboxColumn("UOM", options=["pcs", "kg", "box", "set"], width="small"),
            "Specification": st.column_config.TextColumn("Specification", width="large"),
            "Delivery Location": st.column_config.TextColumn("Delivery Location", width="medium"),
            "Provenance": st.column_config.TextColumn("Origin", disabled=True, width="small")
        }
    )
    st.session_state.rfq_data["line_items"] = edited_items.to_dict(orient="records")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2, 1, 1])
    with f2:
        if st.button("Save draft", type="secondary"):
            st.session_state.rfq_status = "Draft saved"
            st.success("Draft saved successfully.")
    with f3:
        if st.button("Publish RFQ", type="primary"):
            st.session_state.rfq_status = "Published"
            st.session_state.responses_unlocked = True
            st.session_state.stage = "Supplier Responses"
            st.rerun()

# -----------------------------------------------------------------------------
# STAGE 2: SUPPLIER RESPONSES
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Supplier Responses":
    st.markdown("### Supplier responses")
    st.caption("Track supplier submissions, extract quote data and review exceptions before adding them to the comparison.")

    # Dynamic Executive Summary Strip
    responses_rcvd_count = len(st.session_state.uploaded_suppliers)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Responses Received", f"{responses_rcvd_count} / {len(SUPPLIERS)}")
    s2.metric("Complete Quotes", f"{sum(1 for v in calc['supplier_totals'].values() if v['is_complete'])} / {len(SUPPLIERS)}")
    s3.metric("Qualified Suppliers", f"{calc['total_qualified_suppliers']} / {len(SUPPLIERS)}")
    s4.metric("Quote Exceptions", f"{calc['total_line_exceptions']} items")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    st.info("Demo dataset · Preloaded baseline quotes shown below. Uploaded responses override the baseline values.")

    st.markdown("#### Supplier Response Status")
    
    inbox_rows = []
    for sname in SUPPLIERS:
        info = calc["supplier_totals"][sname]
        q_info = calc["qualification_status"][sname]
        
        coverage = f"{info['lines_quoted']} / {info['total_lines']} lines"
        qual_str = "Qualified" if q_info["qualified"] else "Disqualified"
        data_qual = "Complete" if info["is_complete"] else f"{info['total_lines'] - info['lines_quoted']} missing lines"
        receipt_str = "Quote received" if sname in st.session_state.uploaded_suppliers else "Baseline quote loaded"
        
        inbox_rows.append({
            "Supplier": sname,
            "Receipt": receipt_str,
            "Coverage": coverage,
            "Qualification": qual_str,
            "Data Quality": data_qual,
            "Offered Terms": st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Offered Payment Terms", sname].values[0]
        })
        
    st.dataframe(pd.DataFrame(inbox_rows), use_container_width=True, hide_index=True)

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
    # Custom Integrated Ingestion Workspace Box
    st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
    st.markdown("#### Add Supplier Quote")
    st.caption("Upload supplier response file and select target vendor.")
    
    up_col1, up_col2 = st.columns([2.5, 1.5])
    with up_col1:
        uploaded_file = st.file_uploader(
            "Drop supplier quotation here (PDF, XLSX, DOCX, JPG, PNG, TXT)",
            type=["pdf", "xlsx", "docx", "png", "jpg", "txt"],
            label_visibility="collapsed"
        )
    with up_col2:
        supplier_target = st.selectbox("Select supplier:", SUPPLIERS)
        if uploaded_file and st.button("Extract quote data", type="primary"):
            with st.spinner(f"Reading and normalizing quotation for {supplier_target}..."):
                try:
                    file_bytes = uploaded_file.read()
                    
                    if uploaded_file.type in ["image/png", "image/jpeg"]:
                        part = types.Part.from_bytes(data=file_bytes, mime_type=uploaded_file.type)
                        prompt = "Extract supplier quotation pricing into JSON format matching the schema."
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[part, prompt],
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        extraction_summary = res.text
                    else:
                        raw_doc_text = parse_raw_document_content(file_bytes, uploaded_file.name, uploaded_file.type)
                        sys_ext_prompt = f"""
                        You are an expert procurement document parser. Extract line item prices for supplier '{supplier_target}' into JSON.
                        JSON Schema:
                        {{
                           "supplier": "{supplier_target}",
                           "currency": "INR or USD",
                           "extracted_prices": [
                              {{
                                 "line_num": "ITEM-001",
                                 "quoted_price": 22.50,
                                 "currency": "INR",
                                 "quoted_uom": "pcs or 100 pcs or box",
                                 "price_basis": "per unit or per 100",
                                 "confidence": "98%",
                                 "source_reference": "Page 1"
                              }}
                           ]
                        }}
                        """
                        res = client.models.generate_content(
                            model="gemini-2.5-flash", 
                            contents=f"Raw Content:\n{raw_doc_text}\n\n{sys_ext_prompt}",
                            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                        )
                        extraction_summary = res.text

                    parsed_ext = extract_json_from_response(extraction_summary)
                    if "extracted_prices" in parsed_ext and len(parsed_ext["extracted_prices"]) > 0:
                        st.session_state.pending_extraction = {
                            "supplier": supplier_target,
                            "file_name": uploaded_file.name,
                            "parsed": parsed_ext
                        }
                        st.success("Extraction complete. Review extracted quote details below.")
                    else:
                        st.error("No structured line-item prices were extracted. Nothing has been applied.")
                except Exception:
                    st.error("No structured line-item prices were extracted. Nothing has been applied.")
    st.markdown("</div>", unsafe_allow_html=True)

    # RICH EXTRACTION REVIEW PANEL (P0 Granular Extraction Schema)
    if st.session_state.pending_extraction:
        p_data = st.session_state.pending_extraction["parsed"]
        sname = st.session_state.pending_extraction['supplier']
        
        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown(f"#### Review Extracted Quote: **{sname}**")
        st.caption(f"Source file: `{st.session_state.pending_extraction['file_name']}` &nbsp;·&nbsp; Complete audit representation")
        
        if "extracted_prices" in p_data and isinstance(p_data["extracted_prices"], list):
            review_table = []
            for item in p_data["extracted_prices"]:
                lnum = item.get("line_num")
                raw_p = item.get("quoted_price")
                if raw_p is None:
                    raw_p = item.get("price")
                    
                curr = str(item.get("currency", "INR")).upper()
                q_uom = str(item.get("quoted_uom", "pc")).lower()
                conf = item.get("confidence", "95%")
                src_ref = item.get("source_reference", "Document Body")
                
                # Normalization Engine (FX + UOM Scaling)
                if raw_p is not None:
                    val = float(raw_p)
                    basis_desc = "Direct INR"
                    if curr == "USD":
                        val = val * DEMO_FX_RATE
                        basis_desc = "USD → INR"
                    if "100" in q_uom:
                        val = val / 100.0
                        basis_desc += " (/100 → /pc)"
                    norm_price = round(val, 2)
                    quote_str = f"${raw_p:.2f} / pc" if curr == "USD" else f"₹{raw_p:.2f} / {q_uom}"
                    status_str = "Matched"
                else:
                    norm_price = None
                    quote_str = "Unquoted"
                    basis_desc = "None"
                    status_str = "Review"

                review_table.append({
                    "Line #": lnum,
                    "Original Quote": quote_str,
                    "Normalized (INR)": norm_price if norm_price is not None else "—",
                    "Transformation Basis": basis_desc,
                    "Source Reference": src_ref,
                    "Confidence": conf,
                    "Status": status_str
                })
            
            extracted_count = len(review_table)
            st.dataframe(pd.DataFrame(review_table), use_container_width=True, height=220, hide_index=True)
            
            rev_col1, rev_col2 = st.columns([1.5, 1])
            with rev_col1:
                if st.button(f"Apply {extracted_count} extracted values", type="primary"):
                    meta = SUPPLIER_MAP[sname]
                    norm_col = meta["norm_col"]
                    orig_col = meta["orig_col"]
                    status_col = meta["status_col"]
                    
                    for p_item in p_data["extracted_prices"]:
                        lnum = p_item.get("line_num")
                        raw_price = p_item.get("quoted_price")
                        if raw_price is None:
                            raw_price = p_item.get("price")
                            
                        curr = str(p_item.get("currency", "INR")).upper()
                        q_uom = str(p_item.get("quoted_uom", "pc")).lower()
                        
                        if lnum and (raw_price is not None) and norm_col in st.session_state.master_matrix.columns:
                            val = float(raw_price)
                            orig_representation = f"${val:.2f} / pc" if curr == "USD" else f"₹{val:.2f} / {q_uom}"
                            
                            if curr == "USD":
                                val = val * DEMO_FX_RATE
                            if "100" in q_uom:
                                val = val / 100.0
                            norm_val = round(val, 2)
                            
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, norm_col] = norm_val
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, orig_col] = orig_representation
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, status_col] = "CONFIRMED"
                            
                    st.session_state.uploaded_suppliers.add(sname)
                    st.session_state.uploaded_docs_log.append({
                        "file": st.session_state.pending_extraction["file_name"],
                        "supplier": sname,
                        "summary": f"Applied {extracted_count} extracted line items."
                    })
                    st.session_state.pending_extraction = None
                    st.success(f"✓ Added {extracted_count} values for {sname} to comparison dataset.")
                    st.rerun()
            with rev_col2:
                if st.button("Discard extraction", type="secondary"):
                    st.session_state.pending_extraction = None
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption("Data handling notes: Prior-year reference prices were not used as current quotes. USD quotes are normalized using the demo FX rate of ₹83.50/USD.")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← Back to Requirements", type="secondary"):
            st.session_state.stage = "Create RFQ"
            st.rerun()
    with b2:
        if st.button("Continue to Compare Quotes →", type="primary"):
            st.session_state.compare_unlocked = True
            st.session_state.stage = "Compare Bids"
            st.rerun()

# -----------------------------------------------------------------------------
# STAGE 3: COMPARE QUOTES
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Compare Bids":
    st.markdown("### Compare quotes")
    st.caption("Compare normalized unit prices, coverage and qualification compliance across submitted supplier quotes.")

    # Executive Summary Breakdown Strip
    responses_rcvd_count = len(st.session_state.uploaded_suppliers)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Responses Received", f"{responses_rcvd_count} / {len(SUPPLIERS)}")
    c2.metric("Qualified Vendors", f"{calc['total_qualified_suppliers']} / {len(SUPPLIERS)}")
    c3.metric("Complete Quotes", f"{sum(1 for v in calc['supplier_totals'].values() if v['is_complete'])}")
    c4.metric("Quote Exceptions", f"{calc['total_line_exceptions']}")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    st.info("Demo dataset · Preloaded baseline quotes shown below. Uploaded responses override the baseline values.")
    
    # Quoted Value Summary Table
    summary_rows = []
    for sname in SUPPLIERS:
        info = calc["supplier_totals"][sname]
        q_info = calc["qualification_status"][sname]
        spend_str = f"₹{info['total_spend']:,.0f}" if info['is_complete'] else f"Partial (₹{info['total_spend']:,.0f})"
        
        summary_rows.append({
            "Supplier": sname,
            "Coverage": f"{info['lines_quoted']} / {info['total_lines']} lines",
            "Qualification": "Qualified" if q_info['qualified'] else "Disqualified",
            "Data Quality": "Complete" if info['is_complete'] else f"Incomplete ({info['total_lines'] - info['lines_quoted']} unquoted)",
            "Quoted value — available lines": spend_str
        })
        
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    st.caption("Complete responses only are directly comparable at total-quote level.")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
    # Fully Dynamic Issues Drawer
    if calc["dynamic_issue_descriptions"]:
        with st.expander(f"Issues requiring attention · {calc['total_line_exceptions']} lines affected"):
            for issue_desc in calc["dynamic_issue_descriptions"]:
                st.markdown(f"* {issue_desc}")

    tab_comp1, tab_comp2 = st.tabs(["Price comparison matrix", "Qualification checks"])
    
    with tab_comp1:
        m_col1, m_col2 = st.columns([2, 1])
        with m_col1:
            st.session_state.exception_filter = st.selectbox(
                "Filter matrix:",
                ["All line items", "Exceptions & issues only"]
            )
        with m_col2:
            st.markdown("<div style='text-align: right; font-size: 0.8rem; color: #64748B; padding-top: 28px;'>Normalized unit price (INR / unit)</div>", unsafe_allow_html=True)
        
        matrix_display = st.session_state.master_matrix[[
            "Line #", "Description", "Quantity", "UOM",
            "Apex_Norm_INR", "BoxCraft_Norm_INR", "CorruSeal_Norm_INR", "National_Norm_INR", "PackTech_Norm_INR"
        ]].copy()
        
        matrix_display.columns = ["Line #", "Description", "Qty", "UOM", "Apex Packaging", "BoxCraft Ltd", "CorruSeal Global", "National Paper Mills", "PackTech Solutions"]
        
        if st.session_state.exception_filter == "Exceptions & issues only":
            matrix_display = matrix_display[matrix_display["Line #"].isin(calc["exception_line_numbers"])]

        # Replace NaN with clean em-dash string
        matrix_display = matrix_display.fillna("—")

        # Dynamic 3-State Matrix Highlighting (Green = Usable Winner, Amber = Review Required)
        def style_matrix_cells(row):
            styles = [''] * len(row)
            
            # Identify qualified supplier column indices dynamically using SUPPLIERS list
            qual_col_indices = []
            for col_idx in range(4, len(row)):
                sname = SUPPLIERS[col_idx - 4]
                if calc["qualification_status"].get(sname, {}).get("qualified", False):
                    qual_col_indices.append(col_idx)

            valid_prices = {}
            for col_idx in range(4, len(row)):
                val = row.iloc[col_idx]
                sname = SUPPLIERS[col_idx - 4]
                status = str(st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == row["Line #"], SUPPLIER_MAP[sname]["status_col"]].values[0]).upper()
                
                if status == "REVIEW REQUIRED":
                    styles[col_idx] = 'background-color: #FFFBEB; color: #B45309;'  # Amber Review Tint
                elif val != "—" and col_idx in qual_col_indices:
                    try:
                        valid_prices[col_idx] = float(val)
                    except ValueError:
                        pass
                        
            if valid_prices:
                min_col = min(valid_prices, key=valid_prices.get)
                styles[min_col] = 'background-color: #F0FDF4; font-weight: bold; color: #166534;'  # Green Usable Winner
            return styles

        styled_matrix = matrix_display.style.apply(style_matrix_cells, axis=1)
        st.dataframe(styled_matrix, use_container_width=True, height=440, hide_index=True)
        
        st.markdown("""
        <div style="font-size: 0.78rem; color: #64748B; margin-top: 4px;">
            <strong>Legend:</strong> &nbsp;
            <span style="background-color: #F0FDF4; color: #166534; padding: 2px 6px; border-radius: 4px; border: 1px solid #BBF7D0;">Lowest usable qualified price</span> &nbsp;
            <span style="background-color: #FFFBEB; color: #B45309; padding: 2px 6px; border-radius: 4px; border: 1px solid #FEF08A;">Review required</span> &nbsp;
            <span>— Unquoted / Missing</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Normalization: USD → INR at ₹83.50/USD · Quoted prices normalized to requested UOM.")

    with tab_comp2:
        st.markdown("#### Qualification Checks Evaluation")
        st.caption("Mandatory Criteria: ISO 9001 certification required AND 3-year verified defect rate < 0.5%")
        
        qual_summary = []
        for sname in SUPPLIERS:
            q_info = calc["qualification_status"][sname]
            qual_summary.append({
                "Supplier": sname,
                "ISO 9001": "YES" if "YES" in str(q_info["iso"]).upper() else "NO",
                "Defect Rate": q_info["defect"],
                "Qualification": "Qualified" if q_info["qualified"] else "Disqualified",
                "Reason / Notes": q_info["reason"]
            })
        st.dataframe(pd.DataFrame(qual_summary), use_container_width=True, hide_index=True)
        
        with st.expander("View underlying questionnaire evidence matrix"):
            st.dataframe(st.session_state.questionnaire_matrix, use_container_width=True, hide_index=True)

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    cb1, cb2 = st.columns([1, 1])
    with cb1:
        if st.button("← Back to Responses", type="secondary"):
            st.session_state.stage = "Supplier Responses"
            st.rerun()
    with cb2:
        if st.button("Continue to Scenario Analysis →", type="primary"):
            st.session_state.analyze_unlocked = True
            st.session_state.stage = "Analyze & Decide"
            st.rerun()

# -----------------------------------------------------------------------------
# STAGE 4: SCENARIO ANALYSIS
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Analyze & Decide":
    st.markdown("### Scenario analysis")
    st.caption("Evaluate sourcing scenarios using submitted supplier data. Spend calculations follow defined sourcing rules; AI interprets trade-offs and data gaps.")

    st.markdown("#### Common analyses")
    q_col1, q_col2, q_col3 = st.columns(3)
    prompt_choice = None
    if q_col1.button("Lowest qualified split", type="secondary"):
        prompt_choice = "What happens if we split the award across qualified suppliers based on lowest unit price?"
    if q_col2.button("Supplier eligibility", type="secondary"):
        prompt_choice = "Why are certain suppliers excluded from full award scenarios?"
    if q_col3.button("Landed-cost gaps", type="secondary"):
        prompt_choice = "What data is missing to calculate landed cost?"

    user_query = st.text_input(
        "Ask a sourcing question:",
        value=prompt_choice if prompt_choice else "",
        placeholder="e.g. What happens if we split the award across qualified suppliers based on lowest price?"
    )

    if st.button("Run analysis", type="primary"):
        if not user_query:
            st.warning("Please enter a question or select a common analysis shortcut.")
        else:
            with st.spinner("Evaluating sourcing scenario..."):
                matrix_json = st.session_state.master_matrix.to_json(orient="records")
                q_json = st.session_state.questionnaire_matrix.to_json(orient="records")
                
                # Dynamic construction of supplier status strings
                disqualified_list = [f"{s} ({info['reason']})" for s, info in calc['qualification_status'].items() if not info['qualified']]
                incomplete_list = [f"{s} ({info['lines_quoted']}/{info['total_lines']} lines)" for s, info in calc['supplier_totals'].items() if not info['is_complete']]
                
                disqual_str = "; ".join(disqualified_list) if disqualified_list else "None"
                incomp_str = "; ".join(incomplete_list) if incomplete_list else "None"

                delta_direction = "lower" if calc['price_diff'] >= 0 else "higher"

                system_instruction = f"""
                You are an enterprise procurement analysis assistant.
                You are analyzing an RFx dataset of {len(st.session_state.rfq_data['line_items'])} line items across {len(SUPPLIERS)} suppliers.
                
                STRICT GROUNDING RULES:
                - Do NOT invent numerical figures independently.
                - Spend calculations use defined Python sourcing rules:
                  * Lowest Complete Qualified Single Quote: {calc['best_single_name']} at ₹{calc['best_single_spend']:,.0f}
                  * Qualified Split Scenario Spend: ₹{calc['split_spend']:,.0f}
                  * Price Delta vs Lowest Complete Quote: ₹{abs(calc['price_diff']):,.0f} {delta_direction} ({calc['price_diff_pct']}%)
                  * Disqualified Suppliers: {disqual_str}
                  * Incomplete Responses: {incomp_str}
                
                OUTPUT STRUCTURE REQUIREMENT:
                Provide clean JSON response with the following keys:
                {{
                    "headline_answer": "One concise executive sentence.",
                    "key_drivers": ["bullet point 1", "bullet point 2"],
                    "trade_offs": ["bullet point 1", "bullet point 2"],
                    "data_gaps": ["bullet point 1"]
                }}
                """
                
                try:
                    res = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=f"Master Matrix:\n{matrix_json}\n\nQuestionnaire:\n{q_json}\n\nUser Question: {user_query}",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                    parsed_ans = extract_json_from_response(res.text)
                    
                    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
                    st.markdown("#### Analysis Result")
                    st.markdown(f"### {parsed_ans.get('headline_answer', '')}")
                    st.caption(f"Calculated from submitted quote data · Based on {len(st.session_state.rfq_data['line_items'])} line items · {calc['total_qualified_suppliers']} qualified suppliers · Price-only basis")
                    
                    # Query-Specific Contextual Metric Strips
                    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
                    if "landed" in user_query.lower() or "gst" in user_query.lower():
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Missing</div><div class='metric-card-lbl'>GST Rates</div></div>", unsafe_allow_html=True)
                        with m2:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Missing</div><div class='metric-card-lbl'>Freight Costs</div></div>", unsafe_allow_html=True)
                        with m3:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{len(SUPPLIERS)} Vendors</div><div class='metric-card-lbl'>Suppliers Affected</div></div>", unsafe_allow_html=True)
                        with m4:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Unavailable</div><div class='metric-card-lbl'>Landed Basis</div></div>", unsafe_allow_html=True)
                    elif "eligib" in user_query.lower() or "exclude" in user_query.lower() or "qualif" in user_query.lower():
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_qualified_suppliers']} / {len(SUPPLIERS)}</div><div class='metric-card-lbl'>Qualified Vendors</div></div>", unsafe_allow_html=True)
                        with m2:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_disqualified_suppliers']}</div><div class='metric-card-lbl'>Disqualified Vendors</div></div>", unsafe_allow_html=True)
                        with m3:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{sum(1 for v in calc['supplier_totals'].values() if not v['is_complete'])}</div><div class='metric-card-lbl'>Incomplete Quotes</div></div>", unsafe_allow_html=True)
                        with m4:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_line_exceptions']}</div><div class='metric-card-lbl'>Quote Exceptions</div></div>", unsafe_allow_html=True)
                    else:
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>₹{calc['split_spend']:,.0f}</div><div class='metric-card-lbl'>Illustrative Split Spend</div></div>", unsafe_allow_html=True)
                        with m2:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>₹{abs(calc['price_diff']):,.0f} {delta_direction}</div><div class='metric-card-lbl'>Delta vs Lowest Complete Qualified ({calc['price_diff_pct']}%)</div></div>", unsafe_allow_html=True)
                        with m3:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_qualified_suppliers']} / {len(SUPPLIERS)}</div><div class='metric-card-lbl'>Qualified Vendors</div></div>", unsafe_allow_html=True)
                        with m4:
                            st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['unassigned_count']}</div><div class='metric-card-lbl'>Unassigned Lines</div></div>", unsafe_allow_html=True)
                    
                    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        if parsed_ans.get("key_drivers"):
                            st.markdown("**Key drivers**")
                            for kd in parsed_ans["key_drivers"]:
                                st.markdown(f"* {kd}")
                    with c2:
                        if parsed_ans.get("trade_offs"):
                            st.markdown("**Trade-offs & Considerations**")
                            for to in parsed_ans["trade_offs"]:
                                st.markdown(f"* {to}")
                                
                    if parsed_ans.get("data_gaps"):
                        st.markdown("**Data Gaps Identified**")
                        for dg in parsed_ans["data_gaps"]:
                            st.markdown(f"* <span class='badge-review'>Data Gap</span> {dg}", unsafe_allow_html=True)

                except Exception:
                    st.error("Scenario evaluation failed. Please refine query.")

    # Data-Gap / Landed Cost Table (Fully Dynamic Across All Suppliers)
    if user_query and ("landed" in user_query.lower() or "gst" in user_query.lower()):
        st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
        st.markdown("#### Landed Cost Data-Gap Analysis")
        st.warning("Landed cost cannot be calculated due to missing numerical GST rate and freight cost inputs.")
        
        gap_rows = []
        for sname in SUPPLIERS:
            freight_term = st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Freight Responsibility", sname].values[0]
            qual_val = "AVAILABLE" if calc["qualification_status"][sname]["qualified"] else "FAILED"
            
            gap_rows.append({
                "Supplier": sname,
                "Base Unit Price": "AVAILABLE",
                "Normalized INR": "AVAILABLE",
                "Qualification Check": qual_val,
                "Freight Responsibility": freight_term,
                "GST Rate (%)": "MISSING IN SUBMISSION",
                "Freight Cost Amount": "MISSING IN SUBMISSION"
            })
            
        st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

    # Split Allocation Visualization
    if user_query and ("split" in user_query.lower() or "cheapest" in user_query.lower()):
        st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
        st.markdown("#### Spend Distribution by Supplier (Qualified Split Scenario)")
        st.caption("Illustrative price-only allocation — not a final award recommendation. Supplier capacity, freight, lead time and commercial terms are excluded.")
        
        st.dataframe(calc["split_allocation"], use_container_width=True, height=260, hide_index=True)
        
        fig = px.bar(
            calc["split_allocation"],
            x="Awarded Supplier",
            y="Extended Spend (INR)",
            color_discrete_sequence=["#2563EB"],
            template="plotly_white",
            title="Spend Distribution by Supplier"
        )
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
    # Transparent Calculation Basis Explanation Box
    st.caption("Calculation basis: Price-only comparison using quoted unit price × requested quantity. Excludes GST, freight cost amounts, lead time, capacity and other commercial factors.")
    
    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    csv_data = st.session_state.master_matrix.to_csv(index=False).encode('utf-8')
    st.download_button("Download comparison CSV", csv_data, "RFQ_Master_Matrix.csv", "text/csv", type="secondary")
