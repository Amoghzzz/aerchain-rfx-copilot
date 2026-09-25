import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
import datetime
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
# 1. CENTRALIZED CONSTANTS & DESIGN SYSTEM
# -----------------------------------------------------------------------------
DEMO_FX_RATE = 83.50  # USD to INR Demo FX Normalization Rate
PRIMARY_BLUE = "#2563EB"

SUPPLIERS = [
    "Apex Packaging",
    "BoxCraft Ltd",
    "CorruSeal Global",
    "National Paper Mills",
    "PackTech Solutions"
]

SUPPLIER_MAP = {
    "Apex Packaging": {"prefix": "Apex", "orig_col": "Apex_Orig_Price", "norm_col": "Apex_Norm_INR", "status_col": "Apex_Status", "conf_col": "Apex_Confidence", "source_col": "Apex_Source_Ref"},
    "BoxCraft Ltd": {"prefix": "BoxCraft", "orig_col": "BoxCraft_Orig_Price", "norm_col": "BoxCraft_Norm_INR", "status_col": "BoxCraft_Status", "conf_col": "BoxCraft_Confidence", "source_col": "BoxCraft_Source_Ref"},
    "CorruSeal Global": {"prefix": "CorruSeal", "orig_col": "CorruSeal_Orig_Price", "norm_col": "CorruSeal_Norm_INR", "status_col": "CorruSeal_Status", "conf_col": "CorruSeal_Confidence", "source_col": "CorruSeal_Source_Ref"},
    "National Paper Mills": {"prefix": "National", "orig_col": "National_Orig_Price", "norm_col": "National_Norm_INR", "status_col": "National_Status", "conf_col": "National_Confidence", "source_col": "National_Source_Ref"},
    "PackTech Solutions": {"prefix": "PackTech", "orig_col": "PackTech_Orig_Price", "norm_col": "PackTech_Norm_INR", "status_col": "PackTech_Status", "conf_col": "PackTech_Confidence", "source_col": "PackTech_Source_Ref"}
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
    .badge-datagap { background-color: #F8FAFC; color: #475569; border: 1px solid #CBD5E1; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }

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

def parse_safe_numeric_price(val):
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(val))
        res = float(cleaned)
        return res if res > 0 else None
    except Exception:
        return None

# Clear stale analysis snapshot on material state changes (Point #2)
def invalidate_analysis_snapshot():
    st.session_state.last_analysis_result = None
    st.session_state.last_analysis_query = None
    st.session_state.last_analysis_context = None

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
            raise ValueError("PDF parser unavailable in current environment.")
            
    elif mime_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"] or filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls"):
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
            raise ValueError("Spreadsheet parser unavailable in current environment.")

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
            raise ValueError("DOCX parser unavailable in current environment.")

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
            "Apex_Source_Ref": "Demo Baseline", # Updated Provenance Default (Point #5)
            
            "BoxCraft_Orig_Price": f"₹{p2_orig:.2f} / pc" if p2_orig else "NOT QUOTED",
            "BoxCraft_Norm_INR": p2_orig,
            "BoxCraft_Status": "CONFIRMED" if p2_orig else "MISSING",
            "BoxCraft_Confidence": "95%" if p2_orig else "0%",
            "BoxCraft_Source_Ref": "Demo Baseline" if p2_orig else "N/A",
            
            "CorruSeal_Orig_Price": f"${p3_usd:.2f} / pc",
            "CorruSeal_Norm_INR": p3_norm,
            "CorruSeal_Status": "NORMALIZED",
            "CorruSeal_Confidence": "96%",
            "CorruSeal_Source_Ref": "Demo Baseline",
            
            "National_Orig_Price": f"₹{p4_per_100:.2f} / 100 pcs",
            "National_Norm_INR": p4_norm,
            "National_Status": "NORMALIZED" if idx != 20 else "REVIEW REQUIRED",
            "National_Confidence": "88%" if idx != 20 else "58% (Scanned Digit Ambiguity)",
            "National_Source_Ref": "Demo Baseline",
            
            "PackTech_Orig_Price": f"₹{p5_orig:.2f} / pc" if p5_orig else "UNAVAILABLE (Prior-year reference without price)",
            "PackTech_Norm_INR": p5_orig,
            "PackTech_Status": "CONFIRMED" if p5_orig else "MISSING",
            "PackTech_Confidence": "90%" if p5_orig else "0%",
            "PackTech_Source_Ref": "Demo Baseline" if p5_orig else "N/A"
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
        "PackTech Solutions": ["NO", "YES", "2.1% (Exceeds 0.5%)", "1.1M pcs", "Net 45", "Supplier Prepaid (DDP)", "YES", "Bengaluru, KA"]
    }
    return pd.DataFrame(data)

# -----------------------------------------------------------------------------
# 6. PERSISTENT WORKFLOW STATE & DATA SYNCHRONIZATION ENGINE
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

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = True

if "processed_file_hashes" not in st.session_state:
    st.session_state.processed_file_hashes = set()

if "last_analysis_query" not in st.session_state:
    st.session_state.last_analysis_query = None

if "last_analysis_result" not in st.session_state:
    st.session_state.last_analysis_result = None

if "last_analysis_context" not in st.session_state:
    st.session_state.last_analysis_context = None

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

def rfq_matches_demo_baseline():
    canonical_df = pd.DataFrame(get_canonical_30_items())
    current_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
    compare_cols = ["Line #", "Description", "Quantity", "UOM", "Specification", "Delivery Location"]
    
    if not all(col in current_df.columns for col in compare_cols):
        return False
        
    return canonical_df[compare_cols].fillna("").astype(str).equals(
        current_df[compare_cols].fillna("").astype(str)
    )

def sync_rfq_to_master_matrix():
    rfq_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
    base_cols = ["Line #", "Description", "Quantity", "UOM", "Specification", "Delivery Location"]
    
    if not all(col in rfq_df.columns for col in base_cols):
        return
        
    rfq_base = rfq_df[base_cols].copy()
    existing = st.session_state.master_matrix.copy()
    
    supplier_cols = [c for c in existing.columns if c not in base_cols]
    existing_supplier_data = existing[["Line #"] + supplier_cols].copy()
    
    merged = rfq_base.merge(existing_supplier_data, on="Line #", how="left")
    st.session_state.master_matrix = merged

sync_rfq_to_master_matrix()

# -----------------------------------------------------------------------------
# 7. DYNAMIC RULE-BASED QUALIFICATION & SPEND ENGINE (Points #1, #5)
# -----------------------------------------------------------------------------
def calculate_deterministic_spend_engine(df, quest_df, uploaded_suppliers_set, is_demo_mode):
    if is_demo_mode:
        active_suppliers = SUPPLIERS
    else:
        active_suppliers = [s for s in SUPPLIERS if s in uploaded_suppliers_set]

    qualification_status = {}
    for sname in SUPPLIERS:
        if sname in quest_df.columns:
            iso_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "ISO 9001 Certification Attached?", sname].values
            defect_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "3-Year Verified Defect Rate", sname].values
            
            iso_val = str(iso_rows[0]).strip().upper() if len(iso_rows) > 0 else "NO"
            defect_val = defect_rows[0] if len(defect_rows) > 0 else "2.5%"
            
            try:
                defect_num = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(defect_val))[0])
            except Exception:
                defect_num = 1.0
                
            is_iso_valid = (iso_val == "YES")
            is_defect_valid = (defect_num < 0.5)
            is_qualified = is_iso_valid and is_defect_valid
            
            reasons = []
            if not is_iso_valid:
                reasons.append(f"ISO 9001 status ({iso_val}) does not meet mandatory threshold")
            if not is_defect_valid:
                reasons.append(f"Defect rate ({defect_val}) exceeds < 0.5% threshold")
                
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

    for sname in active_suppliers:
        meta = SUPPLIER_MAP[sname]
        norm_col = meta["norm_col"]
        status_col = meta["status_col"]
        
        if norm_col not in df.columns:
            continue
            
        # P0 FIX: Usable rows strictly require CONFIRMED or NORMALIZED (Excludes REVIEW REQUIRED from totals) (Points #1, #5)
        usable_rows = df[
            df[norm_col].notnull() & 
            df[status_col].isin(["CONFIRMED", "NORMALIZED"])
        ]
        
        lines_quoted = len(df[df[norm_col].notnull()])
        has_missing = (df[status_col] == "MISSING").any()
        has_review = (df[status_col] == "REVIEW REQUIRED").any()
        
        total_spend = (usable_rows[norm_col] * usable_rows["Quantity"]).sum()
        is_qual = qualification_status.get(sname, {}).get("qualified", True)
        
        # P0 FIX: Strict Complete Single Quote Definition: 30/30 quoted + 0 review-required (Points #1, #5)
        is_complete = (lines_quoted == len(df)) and (not has_missing) and (not has_review)
        
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
            item_list = ", ".join(unquoted_items[:3]) + (f" +{len(unquoted_items)-3} more" if len(unquoted_items) > 3 else "")
            dynamic_issue_descriptions.append(f"**{sname}:** {len(unquoted_items)} lines missing ({item_list}).")
        if review_items:
            item_lbl = "line" if len(review_items) == 1 else "lines"
            verb_lbl = "needs" if len(review_items) == 1 else "need"
            dynamic_issue_descriptions.append(f"**{sname}:** {len(review_items)} {item_lbl} {verb_lbl} review ({', '.join(review_items)}).")

        supplier_totals[sname] = {
            "total_spend": round(total_spend, 2),
            "lines_quoted": lines_quoted,
            "usable_lines": len(usable_rows),
            "total_lines": len(df),
            "is_complete": is_complete,
            "has_review": has_review,
            "qualified": is_qual,
            "col_name": norm_col,
            "status_col": status_col
        }

    for sname in active_suppliers:
        q_info = qualification_status[sname]
        if not q_info["qualified"]:
            dynamic_issue_descriptions.append(f"**{sname}:** Qualification failed ({q_info['reason']}).")

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
                if status in ["CONFIRMED", "NORMALIZED"]:
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

    total_qualified_suppliers = sum(1 for s in active_suppliers if qualification_status[s]["qualified"])
    total_disqualified_suppliers = sum(1 for s in active_suppliers if not qualification_status[s]["qualified"])

    return {
        "active_suppliers": active_suppliers,
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
st.markdown(f"""
<div class="flat-header">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
        <div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <h2 style="margin: 0; font-size: 1.3rem; font-weight: 600; color: #0F172A;">{st.session_state.rfq_data['title']}</h2>
                <span class="badge-status">{st.session_state.rfq_status}</span>
            </div>
            <div style="font-size: 0.82rem; color: #475569; margin-top: 4px;">
                RFQ-2026-PKG-001 &nbsp;·&nbsp; {len(st.session_state.rfq_data['line_items'])} line items &nbsp;·&nbsp; Due {st.session_state.rfq_data['response_deadline']}
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
            <span class="badge-status">Sourcing Workspace</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

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
                
                raw_items = parsed.get("line_items", [])
                valid_items = []
                for it in raw_items:
                    q_num = parse_safe_numeric_price(it.get("Quantity"))
                    if q_num and q_num > 0 and it.get("Line #") and it.get("Description"):
                        it["Quantity"] = int(q_num)
                        valid_items.append(it)
                        
                if len(valid_items) == 30:
                    st.session_state.rfq_data["title"] = parsed.get("title", "Corrugated Packaging Sourcing")
                    st.session_state.rfq_data["category"] = parsed.get("category", "Packaging Materials")
                    st.session_state.rfq_data["scope"] = parsed.get("scope", "Procurement of corrugated boxes.")
                    st.session_state.rfq_data["delivery_locations"] = parsed.get("delivery_locations", "Bhiwandi & Hosur")
                    st.session_state.rfq_data["payment_terms"] = parsed.get("payment_terms", "Net 60 Days")
                    st.session_state.rfq_data["unclear_specs"] = parsed.get("unclear_specs", [])
                    st.session_state.rfq_data["line_items"] = valid_items
                    sync_rfq_to_master_matrix()
                    invalidate_analysis_snapshot()
                    st.session_state.rfq_generated = True
                    st.session_state.rfq_status = "Draft ready"
                    st.success("RFQ draft created successfully.")
                else:
                    raise ValueError("AI generated invalid RFQ line items.")
            except Exception:
                st.session_state.rfq_data["line_items"] = get_canonical_30_items()
                st.session_state.rfq_data["unclear_specs"] = [
                    "Price Validity: Mandatory duration not explicitly specified in prompt (Recommended: 60 Days)",
                    "Buffer Lead Time: Volume spike buffer lead time not specified for peak season"
                ]
                sync_rfq_to_master_matrix()
                invalidate_analysis_snapshot()
                st.warning("Reverted to standard canonical RFQ draft baseline.")
                st.session_state.rfq_generated = True

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
    if st.session_state.rfq_data["unclear_specs"]:
        st.markdown("#### Needs Your Review")
        st.caption(f"{len(st.session_state.rfq_data['unclear_specs'])} items need confirmation. You can still publish and complete these later:")
        
        rev_cols = st.columns(min(len(st.session_state.rfq_data["unclear_specs"]), 3))
        for idx, spec_item in enumerate(st.session_state.rfq_data["unclear_specs"]):
            with rev_cols[idx % len(rev_cols)]:
                st.warning(f"**Attention Item {idx+1}**\n\n{spec_item}")
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
            "Quantity": st.column_config.NumberColumn("Quantity", format="%d", min_value=1, width="medium"),
            "UOM": st.column_config.SelectboxColumn("UOM", options=["pcs", "kg", "box", "set"], width="small"),
            "Specification": st.column_config.TextColumn("Specification", width="large"),
            "Delivery Location": st.column_config.TextColumn("Delivery Location", width="medium"),
            "Provenance": st.column_config.TextColumn("Origin", disabled=True, width="small")
        }
    )
    
    has_invalid_qty = (edited_items["Quantity"] <= 0).any()
    if has_invalid_qty:
        st.error("⚠ Invalid Quantity detected: All line item quantities must be greater than 0.")
        
    st.session_state.rfq_data["line_items"] = edited_items.to_dict(orient="records")
    sync_rfq_to_master_matrix()
    invalidate_analysis_snapshot()

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2, 1, 1])
    with f2:
        if st.button("Save draft", type="secondary"):
            st.session_state.rfq_status = "Draft saved"
            st.success("Draft saved successfully.")
    with f3:
        if st.button("Publish RFQ", type="primary", disabled=has_invalid_qty):
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

    demo_c1, demo_c2 = st.columns([3, 1])
    with demo_c1:
        if st.session_state.demo_mode:
            st.info("💡 **Demo Mode ON:** Preloaded baseline quotes are included for demonstration. Uploaded supplier values replace baseline values for validated lines.")
        else:
            st.success("🔒 **Strict Live Mode:** Only uploaded supplier quotes participate in comparison and scenario calculations.")
    with demo_c2:
        new_demo_mode = st.toggle("Demo Mode — Include baseline supplier data", value=st.session_state.demo_mode)
        if new_demo_mode != st.session_state.demo_mode:
            st.session_state.demo_mode = new_demo_mode
            invalidate_analysis_snapshot()
            st.rerun()

    # Strengthened Demo Baseline Mismatch Banner (Point #4)
    if st.session_state.demo_mode and not rfq_matches_demo_baseline():
        st.warning("⚠️ **Demo Baseline Specification Mismatch:** Baseline supplier prices were generated for original canonical RFQ requirements. Revised specifications or quantities may render baseline prices unsuitable for sourcing decisions. Use uploaded supplier responses for revised requirements.")

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    responses_rcvd_count = len(st.session_state.uploaded_suppliers)
    s1, s2, s3, s4 = st.columns(4)
    if st.session_state.demo_mode:
        s1.metric("Supplier Submissions", f"{responses_rcvd_count} / {len(SUPPLIERS)}")
        s2.metric("Baseline Quotes Available", f"5 / 5")
    else:
        s1.metric("Responses Received", f"{responses_rcvd_count} / {len(SUPPLIERS)}")
        s2.metric("Complete Quotes", f"{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])} / {len(calc['active_suppliers'])}")
    s3.metric("Qualified Suppliers", f"{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}")
    s4.metric("Exception Lines", f"{calc['total_line_exceptions']} items")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)

    st.markdown("#### Supplier Response Status")
    
    inbox_rows = []
    for sname in SUPPLIERS:
        is_active = sname in calc["active_suppliers"]
        info = calc["supplier_totals"].get(sname, {"lines_quoted": 0, "total_lines": len(st.session_state.master_matrix), "is_complete": False})
        q_info = calc["qualification_status"].get(sname, {"qualified": False})
        
        coverage = f"{info['lines_quoted']} / {info['total_lines']} lines" if is_active else "Excluded (Not Uploaded)"
        qual_str = "Qualified" if q_info["qualified"] else "Disqualified"
        data_qual = "Complete" if info["is_complete"] else ("Review Required" if info.get("has_review") else "Incomplete / Missing")
        receipt_str = "Quote received" if sname in st.session_state.uploaded_suppliers else ("Baseline loaded" if st.session_state.demo_mode else "Not submitted")
        
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
            file_bytes = uploaded_file.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            
            if file_hash in st.session_state.processed_file_hashes:
                st.warning("⚠ Duplicate file detected. This document has already been processed and applied.")
            else:
                with st.spinner(f"Reading and normalizing quotation for {supplier_target}..."):
                    try:
                        unified_schema_prompt = f"""
                        You are an expert procurement document parser. Extract line item prices for supplier '{supplier_target}' into JSON.
                        JSON Schema required:
                        {{
                           "detected_supplier_header": "string (name of supplier found in document text)",
                           "supplier": "{supplier_target}",
                           "currency": "INR or USD",
                           "extracted_prices": [
                              {{
                                 "line_num": "ITEM-001",
                                 "quoted_price": 22.50,
                                 "currency": "INR",
                                 "original_quote_text": "string (exact verbatim text from document, e.g. '$45 / carton of 100 pcs')",
                                 "quoted_uom": "pcs or 100 pcs or box or carton",
                                 "price_basis_quantity": 1.0,
                                 "price_basis_uom": "pcs",
                                 "confidence": "98%",
                                 "source_reference": "Page 1"
                              }}
                           ]
                        }}
                        """
                        
                        if uploaded_file.type in ["image/png", "image/jpeg"]:
                            part = types.Part.from_bytes(data=file_bytes, mime_type=uploaded_file.type)
                            res = client.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=[part, unified_schema_prompt],
                                config=types.GenerateContentConfig(response_mime_type="application/json")
                            )
                        else:
                            raw_doc_text = parse_raw_document_content(file_bytes, uploaded_file.name, uploaded_file.type)
                            res = client.models.generate_content(
                                model="gemini-2.5-flash", 
                                contents=f"Raw Content:\n{raw_doc_text}\n\n{unified_schema_prompt}",
                                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                            )

                        parsed_ext = extract_json_from_response(res.text)
                        
                        detected_vendor = parsed_ext.get("detected_supplier_header", "")
                        has_mismatch = bool(detected_vendor and supplier_target.lower() not in detected_vendor.lower())

                        if "extracted_prices" in parsed_ext and len(parsed_ext["extracted_prices"]) > 0:
                            st.session_state.pending_extraction = {
                                "supplier": supplier_target,
                                "file_name": uploaded_file.name,
                                "file_hash": file_hash,
                                "has_mismatch": has_mismatch,
                                "detected_vendor": detected_vendor,
                                "parsed": parsed_ext
                            }
                            st.success("Extraction complete. Review extracted quote details below.")
                        else:
                            st.error("No structured line-item prices were extracted. Nothing has been applied.")
                    except ValueError as ve:
                        st.error(f"Environment Error: {str(ve)}")
                    except Exception:
                        st.error("Could not parse quotation details. Please verify file formatting.")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.pending_extraction:
        p_data = st.session_state.pending_extraction["parsed"]
        sname = st.session_state.pending_extraction['supplier']
        has_mismatch = st.session_state.pending_extraction.get('has_mismatch', False)
        detected_vendor = st.session_state.pending_extraction.get('detected_vendor', '')
        
        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown(f"#### Review Extracted Quote: **{sname}**")
        st.caption(f"Source file: `{st.session_state.pending_extraction['file_name']}` &nbsp;·&nbsp; Complete audit representation")
        
        confirm_override = True
        if has_mismatch:
            st.error(f"⚠ **Supplier Header Mismatch:** Selected target vendor is **{sname}**, but document header indicates **'{detected_vendor}'**.")
            confirm_override = st.checkbox(f"Confirm: Apply quote to **{sname}** despite document header mismatch", value=False)

        valid_rfq_lines = {it["Line #"] for it in st.session_state.rfq_data["line_items"]}
        seen_lines = set()
        
        review_table = []
        matched_count = 0
        rejected_count = 0

        for item in p_data.get("extracted_prices", []):
            lnum = item.get("line_num")
            raw_p_uncleaned = item.get("quoted_price") if item.get("quoted_price") is not None else item.get("price")
            raw_p = parse_safe_numeric_price(raw_p_uncleaned)
            
            curr = str(item.get("currency", "INR")).upper()
            q_uom = str(item.get("quoted_uom", "pc")).lower()
            orig_verbatim = item.get("original_quote_text", "")
            
            try:
                basis_qty = float(item.get("price_basis_quantity", 1.0) or 1.0)
                is_valid_basis = basis_qty > 0
            except Exception:
                basis_qty = 1.0
                is_valid_basis = False
            
            conf_str = str(item.get("confidence", "95%"))
            try:
                conf_num = float(re.findall(r"\d+", conf_str)[0])
            except Exception:
                conf_num = 95.0
            src_ref = item.get("source_reference", "Document Body")
            
            is_known_currency = curr in ["INR", "USD"]
            if curr == "USD":
                fx = DEMO_FX_RATE
            else:
                fx = 1.0
                
            is_valid_line = lnum in valid_rfq_lines
            is_duplicate = lnum in seen_lines
            is_valid_price = (raw_p is not None) and (raw_p > 0)
            
            if is_valid_line and not is_duplicate and is_valid_price:
                seen_lines.add(lnum)
                matched_count += 1
                
                norm_price = round((raw_p * fx) / (basis_qty if is_valid_basis else 1.0), 2)
                is_normalized = (curr == "USD") or (basis_qty != 1.0)
                
                if conf_num < 90.0 or not is_valid_basis or not is_known_currency:
                    status_str = "REVIEW REQUIRED"
                elif is_normalized:
                    status_str = "NORMALIZED"
                else:
                    status_str = "CONFIRMED"
                    
                basis_desc = "Direct INR"
                if curr == "USD":
                    basis_desc = "USD → INR"
                if basis_qty != 1.0 and is_valid_basis:
                    basis_desc += f" (/{basis_qty:g} → /pc)"
                if not is_known_currency:
                    basis_desc += f" (Unsupported currency: {curr})"
                    
                quote_str = orig_verbatim if orig_verbatim else (f"${raw_p:.2f} / pc" if curr == "USD" else f"₹{raw_p:.2f} / {q_uom}")
            else:
                rejected_count += 1
                status_str = "REJECTED (Duplicate / Invalid Line / Zero Price)"
                norm_price = None
                quote_str = orig_verbatim if orig_verbatim else f"{raw_p_uncleaned} ({curr})"
                basis_desc = "Rejected"

            review_table.append({
                "Line #": lnum,
                "Original Quote": quote_str,
                "Normalized (INR)": norm_price if norm_price is not None else "—",
                "Transformation Basis": basis_desc,
                "Source Reference": src_ref,
                "Confidence": conf_str,
                "Validation Status": status_str,
                "Response Source": "Supplier Submitted"
            })
        
        extracted_total = len(review_table)
        st.dataframe(pd.DataFrame(review_table), use_container_width=True, height=220, hide_index=True)
        st.caption(f"Extraction Summary: **{extracted_total} extracted** · **{matched_count} matched & validated** · **{rejected_count} rejected**")
        st.caption("ℹ Review required values can be applied to the comparison matrix for visibility but are excluded from sourcing calculations until validated.")
        
        rev_col1, rev_col2 = st.columns([1.5, 1])
        with rev_col1:
            if st.button(f"Apply {matched_count} validated values", type="primary", disabled=(matched_count == 0 or not confirm_override)):
                meta = SUPPLIER_MAP[sname]
                norm_col = meta["norm_col"]
                orig_col = meta["orig_col"]
                status_col = meta["status_col"]
                conf_col = meta["conf_col"]
                source_col = meta["source_col"]
                
                for row_entry in review_table:
                    if "REJECTED" not in row_entry["Validation Status"]:
                        lnum = row_entry["Line #"]
                        norm_val = row_entry["Normalized (INR)"]
                        orig_rep = row_entry["Original Quote"]
                        status_val = row_entry["Validation Status"]
                        conf_val = row_entry["Confidence"]
                        src_val = row_entry["Source Reference"]
                        
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, norm_col] = norm_val
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, orig_col] = orig_rep
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, status_col] = status_val
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, conf_col] = conf_val
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, source_col] = src_val
                        
                st.session_state.uploaded_suppliers.add(sname)
                st.session_state.processed_file_hashes.add(st.session_state.pending_extraction["file_hash"])
                st.session_state.uploaded_docs_log.append({
                    "file": st.session_state.pending_extraction["file_name"],
                    "supplier": sname,
                    "summary": f"Applied {matched_count} validated line items."
                })
                st.session_state.pending_extraction = None
                invalidate_analysis_snapshot()
                st.success(f"✓ Added {matched_count} validated values for {sname} to comparison matrix.")
                st.rerun()
        with rev_col2:
            if st.button("Discard extraction", type="secondary"):
                st.session_state.pending_extraction = None
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

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

    demo_c1, demo_c2 = st.columns([3, 1])
    with demo_c1:
        if st.session_state.demo_mode:
            st.info("💡 **Demo Mode ON:** Preloaded baseline quotes are included for demonstration. Uploaded supplier values replace baseline values for validated lines.")
        else:
            st.success("🔒 **Strict Live Mode:** Displaying only uploaded supplier responses.")
    with demo_c2:
        new_demo_mode = st.toggle("Demo Mode — Include baseline supplier data", value=st.session_state.demo_mode)
        if new_demo_mode != st.session_state.demo_mode:
            st.session_state.demo_mode = new_demo_mode
            invalidate_analysis_snapshot()
            st.rerun()

    if st.session_state.demo_mode and not rfq_matches_demo_baseline():
        st.warning("⚠️ **Demo Baseline Specification Mismatch:** Baseline supplier prices were generated for original canonical RFQ requirements. Revised specifications or quantities may render baseline prices unsuitable for sourcing decisions. Use uploaded supplier responses for revised requirements.")

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    responses_rcvd_count = len(st.session_state.uploaded_suppliers)
    c1, c2, c3, c4 = st.columns(4)
    if st.session_state.demo_mode:
        c1.metric("Supplier Submissions", f"{responses_rcvd_count} / {len(SUPPLIERS)}")
        c2.metric("Baseline Quotes Available", f"5 / 5")
    else:
        c1.metric("Responses Received", f"{responses_rcvd_count} / {len(SUPPLIERS)}")
        c2.metric("Complete Quotes", f"{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])}")
    c3.metric("Qualified Vendors", f"{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}")
    c4.metric("Exception Lines", f"{calc['total_line_exceptions']}")

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)

    summary_rows = []
    for sname in calc["active_suppliers"]:
        info = calc["supplier_totals"][sname]
        q_info = calc["qualification_status"][sname]
        spend_str = f"₹{info['total_spend']:,.0f}" if info['is_complete'] else (f"Partial (₹{info['total_spend']:,.0f})" if info['usable_lines'] > 0 else "No Usable Quotes")
        
        summary_rows.append({
            "Supplier": sname,
            "Response Source": "Supplier Submitted" if sname in st.session_state.uploaded_suppliers else "Demo Baseline",
            "Coverage": f"{info['lines_quoted']} / {info['total_lines']} lines",
            "Qualification": "Qualified" if q_info['qualified'] else "Disqualified",
            "Data Quality": "Complete" if info['is_complete'] else ("Review Required" if info['has_review'] else f"Incomplete ({info['total_lines'] - info['lines_quoted']} unquoted)"),
            "Quoted value — usable lines": spend_str
        })
        
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
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
                ["All line items", "Quoted lines with exceptions"]
            )
        with m_col2:
            st.markdown("<div style='text-align: right; font-size: 0.8rem; color: #64748B; padding-top: 28px;'>Normalized unit price (INR / unit)</div>", unsafe_allow_html=True)
        
        matrix_cols = ["Line #", "Description", "Quantity", "UOM"]
        for sname in calc["active_suppliers"]:
            matrix_cols.append(SUPPLIER_MAP[sname]["norm_col"])
            
        matrix_display = st.session_state.master_matrix[matrix_cols].copy()
        
        col_rename_map = {"Quantity": "Qty"}
        for sname in calc["active_suppliers"]:
            col_rename_map[SUPPLIER_MAP[sname]["norm_col"]] = sname
        matrix_display = matrix_display.rename(columns=col_rename_map)
        
        if st.session_state.exception_filter == "Quoted lines with exceptions":
            matrix_display = matrix_display[matrix_display["Line #"].isin(calc["exception_line_numbers"])]

        matrix_display = matrix_display.fillna("—")

        def style_matrix_cells(row):
            styles = [''] * len(row)
            
            qual_col_indices = []
            for col_idx in range(4, len(row)):
                sname = calc["active_suppliers"][col_idx - 4]
                if calc["qualification_status"].get(sname, {}).get("qualified", False):
                    qual_col_indices.append(col_idx)

            valid_prices = {}
            for col_idx in range(4, len(row)):
                val = row.iloc[col_idx]
                sname = calc["active_suppliers"][col_idx - 4]
                status = str(st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == row["Line #"], SUPPLIER_MAP[sname]["status_col"]].values[0]).upper()
                
                if status == "REVIEW REQUIRED":
                    styles[col_idx] = 'background-color: #FFFBEB; color: #B45309;'
                elif val != "—" and col_idx in qual_col_indices:
                    try:
                        valid_prices[col_idx] = float(val)
                    except ValueError:
                        pass
                        
            if valid_prices:
                min_col = min(valid_prices, key=valid_prices.get)
                styles[min_col] = 'background-color: #F0FDF4; font-weight: bold; color: #166534;'
            return styles

        styled_matrix = matrix_display.style.apply(style_matrix_cells, axis=1)
        st.dataframe(styled_matrix, use_container_width=True, height=440, hide_index=True)
        
        st.markdown("""
        <div style="font-size: 0.78rem; color: #64748B; margin-top: 4px;">
            <strong>Legend:</strong> &nbsp;
            <span style="background-color: #F0FDF4; color: #166534; padding: 2px 6px; border-radius: 4px; border: 1px solid #BBF7D0;">Lowest usable qualified price for this line — price comparison only</span> &nbsp;
            <span style="background-color: #FFFBEB; color: #B45309; padding: 2px 6px; border-radius: 4px; border: 1px solid #FEF08A;">Review required (excluded from sourcing)</span> &nbsp;
            <span>— Unquoted / Missing</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Normalization: USD → INR at ₹83.50/USD · Quoted prices normalized to requested UOM. Review required values are displayed for visibility but excluded from sourcing calculations.")

    with tab_comp2:
        st.markdown("#### Qualification Checks Evaluation")
        st.caption("Mandatory Criteria: ISO 9001 certification required AND 3-year verified defect rate < 0.5%")
        
        qual_summary = []
        for sname in calc["active_suppliers"]:
            q_info = calc["qualification_status"][sname]
            qual_summary.append({
                "Supplier": sname,
                "ISO 9001": q_info["iso"],
                "Defect Rate": q_info["defect"],
                "Qualification": "Qualified" if q_info["qualified"] else "Disqualified",
                "Reason / Notes": q_info["reason"]
            })
        st.dataframe(pd.DataFrame(qual_summary), use_container_width=True, hide_index=True)

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
    st.caption("Evaluate sourcing scenarios using available supplier quote data. Spend calculations follow defined sourcing rules; AI interprets trade-offs and data gaps.")

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
        value=prompt_choice if prompt_choice else (st.session_state.last_analysis_query if st.session_state.last_analysis_query else ""),
        placeholder="e.g. What happens if we split the award across qualified suppliers based on lowest price?"
    )

    if st.button("Run analysis", type="primary"):
        if not user_query:
            st.warning("Please enter a question or select a common analysis shortcut.")
        else:
            with st.spinner("Evaluating sourcing scenario..."):
                matrix_json = st.session_state.master_matrix.to_json(orient="records")
                q_json = st.session_state.questionnaire_matrix.to_json(orient="records")
                
                disqualified_list = [f"{s} ({info['reason']})" for s, info in calc['qualification_status'].items() if (s in calc['active_suppliers'] and not info['qualified'])]
                disqual_str = "; ".join(disqualified_list) if disqualified_list else "None"
                delta_direction = "lower" if calc['price_diff'] >= 0 else "higher"

                system_instruction = f"""
                You are an enterprise procurement analysis assistant.
                You are analyzing an RFx dataset of {len(st.session_state.rfq_data['line_items'])} line items across active suppliers: {', '.join(calc['active_suppliers'])}.
                
                STRICT GROUNDING RULES:
                - Do NOT invent numerical figures independently.
                - Only make supplier-specific factual claims directly supported by the provided data.
                - Do not characterize a supplier as better or worse unless tied to an explicit metric.
                - Spend calculations use defined Python sourcing rules:
                  * Lowest Complete Qualified Single Quote: {calc['best_single_name']} at ₹{calc['best_single_spend']:,.0f}
                  * Qualified Split Scenario Spend: ₹{calc['split_spend']:,.0f} (Unassigned lines: {calc['unassigned_count']})
                  * Price Delta vs Lowest Complete Quote: ₹{abs(calc['price_diff']):,.0f} {delta_direction} ({calc['price_diff_pct']}%)
                  * Disqualified Suppliers: {disqual_str}
                
                OUTPUT STRUCTURE REQUIREMENT:
                Provide clean JSON response:
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
                    
                    # Store complete analysis snapshot context with timestamp (Points #2, #8)
                    st.session_state.last_analysis_query = user_query
                    st.session_state.last_analysis_result = parsed_ans
                    st.session_state.last_analysis_context = {
                        "timestamp": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
                        "demo_mode": st.session_state.demo_mode,
                        "active_count": len(calc["active_suppliers"]),
                        "line_count": len(st.session_state.rfq_data["line_items"]),
                        "qual_count": calc["total_qualified_suppliers"],
                        "split_spend": calc["split_spend"],
                        "best_single_spend": calc["best_single_spend"],
                        "price_diff": calc["price_diff"],
                        "price_diff_pct": calc["price_diff_pct"],
                        "unassigned_count": calc["unassigned_count"]
                    }

                except Exception:
                    st.error("Scenario evaluation failed. Please refine query.")

    if st.session_state.last_analysis_result:
        parsed_ans = st.session_state.last_analysis_result
        active_query = st.session_state.last_analysis_query
        ctx = st.session_state.last_analysis_context or {
            "timestamp": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
            "demo_mode": st.session_state.demo_mode,
            "active_count": len(calc["active_suppliers"]),
            "line_count": len(st.session_state.rfq_data["line_items"]),
            "qual_count": calc["total_qualified_suppliers"],
            "split_spend": calc["split_spend"],
            "best_single_spend": calc["best_single_spend"],
            "price_diff": calc["price_diff"],
            "price_diff_pct": calc["price_diff_pct"],
            "unassigned_count": calc["unassigned_count"]
        }
        
        calc_provenance_str = "baseline + submitted supplier data · Demo Mode" if ctx["demo_mode"] else "submitted supplier data only · Strict Live Mode"
        
        st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
        st.markdown("#### Analysis Result")
        st.markdown(f"### {parsed_ans.get('headline_answer', '')}")
        
        # Explicit Audit Execution Timestamp (Point #8)
        st.caption(f"Analysis generated: **{ctx.get('timestamp', 'Recent')}** · Dataset: {calc_provenance_str} · {ctx['active_count']} active suppliers · {ctx['line_count']} RFQ lines · Price-only basis")
        
        st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
        q_lower = active_query.lower()
        
        if "landed" in q_lower or "gst" in q_lower or "freight" in q_lower:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Missing</div><div class='metric-card-lbl'>GST Rates</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Missing</div><div class='metric-card-lbl'>Freight Costs</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{len(calc['active_suppliers'])} Vendors</div><div class='metric-card-lbl'>Suppliers Affected</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Unavailable</div><div class='metric-card-lbl'>Landed Basis</div></div>", unsafe_allow_html=True)
                
        elif "eligib" in q_lower or "exclude" in q_lower or "qualif" in q_lower:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}</div><div class='metric-card-lbl'>Qualified Vendors</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_disqualified_suppliers']}</div><div class='metric-card-lbl'>Disqualified Vendors</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{sum(1 for k in calc['active_suppliers'] if not calc['supplier_totals'][k]['is_complete'])}</div><div class='metric-card-lbl'>Incomplete Quotes</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_line_exceptions']}</div><div class='metric-card-lbl'>Exception Lines</div></div>", unsafe_allow_html=True)
                
        elif "payment" in q_lower or "term" in q_lower:
            terms_series = st.session_state.questionnaire_matrix.loc[
                st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Offered Payment Terms",
                calc["active_suppliers"]
            ].iloc[0]
            term_counts = terms_series.value_counts().to_dict()
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{term_counts.get('Net 60', 0)} Vendors</div><div class='metric-card-lbl'>Net 60 Terms</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{term_counts.get('Net 30', 0)} Vendors</div><div class='metric-card-lbl'>Net 30 Terms</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{term_counts.get('Net 45', 0)} Vendors</div><div class='metric-card-lbl'>Net 45 Terms</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Net 60</div><div class='metric-card-lbl'>RFQ Benchmark</div></div>", unsafe_allow_html=True)

        elif "capacity" in q_lower or "volume" in q_lower:
            cap_series = st.session_state.questionnaire_matrix.loc[
                st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Monthly Packaging Capacity",
                calc["active_suppliers"]
            ].iloc[0]
            
            # Dynamic Mixed-UOM Aggregate Safeguard (Point #3)
            rfq_uoms = set(it["UOM"] for it in st.session_state.rfq_data["line_items"])
            if len(rfq_uoms) == 1:
                single_uom = list(rfq_uoms)[0]
                total_req_units = sum(it["Quantity"] for it in st.session_state.rfq_data["line_items"])
                vol_metric_val = f"{total_req_units:,} {single_uom}"
            else:
                vol_metric_val = f"Mixed UOMs ({len(st.session_state.rfq_data['line_items'])} lines)"

            cap_nums = []
            for v in cap_series.values:
                try:
                    num = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(v))[0])
                    cap_nums.append(num)
                except Exception:
                    pass
            max_cap_str = f"{max(cap_nums):.1f}M pcs/mo" if cap_nums else "1.5M pcs/mo"

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{vol_metric_val}</div><div class='metric-card-lbl'>Required RFQ Volume</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{max_cap_str}</div><div class='metric-card-lbl'>Highest Monthly Cap</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Monthly</div><div class='metric-card-lbl'>Capacity Basis</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>Reference</div><div class='metric-card-lbl'>Assessment Status</div></div>", unsafe_allow_html=True)
            st.caption("ℹ Supplier capacity is reported monthly. RFQ fulfillment period is not specified, so capacity sufficiency cannot be conclusively determined.")

        elif "split" in q_lower or "cheapest" in q_lower or "award" in q_lower or "lowest" in q_lower:
            m1, m2, m3, m4 = st.columns(4)
            assigned_lines_count = ctx['line_count'] - ctx['unassigned_count']
            spend_label = f"₹{ctx['split_spend']:,.0f}" if ctx['unassigned_count'] == 0 else f"Partial: ₹{ctx['split_spend']:,.0f}"
            delta_label = f"₹{abs(ctx['price_diff']):,.0f} {'lower' if ctx['price_diff'] >= 0 else 'higher'}" if ctx['unassigned_count'] == 0 else "Unavailable"
            
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{spend_label}</div><div class='metric-card-lbl'>Split Spend ({assigned_lines_count}/{ctx['line_count']} lines)</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{delta_label}</div><div class='metric-card-lbl'>Delta vs Complete Qualified</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{ctx['qual_count']} / {ctx['active_count']}</div><div class='metric-card-lbl'>Qualified Vendors</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{ctx['unassigned_count']}</div><div class='metric-card-lbl'>Unassigned Lines</div></div>", unsafe_allow_html=True)
            
            if ctx['unassigned_count'] > 0:
                st.caption("⚠ **Note:** Price delta is unavailable because 1 or more line items have no usable qualified quote and are excluded from the illustrative split calculation.")

        else:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{len(calc['active_suppliers'])} / {len(SUPPLIERS)}</div><div class='metric-card-lbl'>Active Suppliers</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])}</div><div class='metric-card-lbl'>Complete Quotes</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_qualified_suppliers']}</div><div class='metric-card-lbl'>Qualified Suppliers</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='metric-card'><div class='metric-card-val'>{calc['total_line_exceptions']}</div><div class='metric-card-lbl'>Exception Lines</div></div>", unsafe_allow_html=True)
        
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
                    
        # Dedicated Data Gap Badge Styling (Point #6)
        if parsed_ans.get("data_gaps"):
            st.markdown("**Data Gaps Identified**")
            for dg in parsed_ans["data_gaps"]:
                st.markdown(f"* <span class='badge-datagap'>Data Gap</span> {dg}", unsafe_allow_html=True)

        if "landed" in q_lower or "gst" in q_lower:
            st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
            st.markdown("#### Landed Cost Data-Gap Analysis")
            st.warning("Landed cost cannot be calculated due to missing numerical GST rate and freight cost inputs.")
            
            gap_rows = []
            for sname in calc["active_suppliers"]:
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

        if "split" in q_lower or "cheapest" in q_lower:
            st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
            # Explicit Illustrative Title Wording (Point #7)
            st.markdown("#### Illustrative Price-Only Split")
            st.caption("Spend distribution by supplier under lowest unit price allocation — not a final award recommendation. Supplier capacity, freight, lead time and commercial terms are excluded.")
            
            st.dataframe(calc["split_allocation"], use_container_width=True, height=260, hide_index=True)
            
            fig = px.bar(
                calc["split_allocation"],
                x="Awarded Supplier",
                y="Extended Spend (INR)",
                color_discrete_sequence=[PRIMARY_BLUE],
                template="plotly_white",
                title="Spend Distribution by Supplier"
            )
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    st.caption("Calculation basis: Price-only comparison using quoted unit price × requested quantity. Excludes GST, freight cost amounts, lead time, capacity and other commercial factors.")
    
    st.markdown("<div class='section-spacing'></div>", unsafe_allow_html=True)
    
    # Clean Audit Provenance Export (Point #5)
    audit_export_rows = []
    for idx, row in st.session_state.master_matrix.iterrows():
        for sname in calc["active_suppliers"]:
            meta = SUPPLIER_MAP[sname]
            audit_export_rows.append({
                "Line #": row["Line #"],
                "Description": row["Description"],
                "Quantity": row["Quantity"],
                "UOM": row["UOM"],
                "Supplier": sname,
                "Original Quote": row.get(meta["orig_col"], "—"),
                "Normalized Unit Price (INR)": row.get(meta["norm_col"], "—"),
                "Validation Status": row.get(meta["status_col"], "—"),
                "Confidence": row.get(meta["conf_col"], "—"),
                "Source Reference": row.get(meta["source_col"], "Demo Baseline"), # Clear Default Provenance
                "Response Source": "Supplier Submitted" if sname in st.session_state.uploaded_suppliers else "Demo Baseline",
                "Qualification Status": "Qualified" if calc["qualification_status"][sname]["qualified"] else "Disqualified"
            })
            
    audit_csv_data = pd.DataFrame(audit_export_rows).to_csv(index=False).encode('utf-8')
    st.download_button("Download comparison & audit trail CSV", audit_csv_data, "RFQ_Audit_Master_Matrix.csv", "text/csv", type="secondary")
