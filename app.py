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

# =============================================================================
# DESIGN SYSTEM TOKENS & CONSTANTS
# =============================================================================
DEMO_FX_RATE = 83.50  # USD to INR Demo FX Normalization Rate

DESIGN_SYSTEM = {
    "colors": {
        "bg_app": "#F8FAFC",
        "surface_card": "#FFFFFF",
        "border_subtle": "#E2E8F0",
        "border_strong": "#CBD5E1",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "text_muted": "#64748B",
        "accent_primary": "#2563EB",
        "accent_hover": "#1D4ED8",
        "status_success_bg": "#F0FDF4",
        "status_success_text": "#166534",
        "status_success_border": "#BBF7D0",
        "status_warning_bg": "#FFFBEB",
        "status_warning_text": "#B45309",
        "status_warning_border": "#FEF08A",
        "status_danger_bg": "#FEF2F2",
        "status_danger_text": "#991B1B",
        "status_danger_border": "#FECACA",
        "status_info_bg": "#F0F9FF",
        "status_info_text": "#0369A1",
        "status_info_border": "#BAE6FD"
    },
    "typography": {
        "font_family": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    },
    "radius": {
        "sm": "4px",
        "md": "6px",
        "lg": "8px"
    }
}

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

# =============================================================================
# PAGE CONFIGURATION & ENTERPRISE SaaS STYLING ARCHITECTURE
# =============================================================================
st.set_page_config(
    page_title="Aerchain | Procurement Intelligence Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(f"""
    <style>
    /* ------------------------------------------------------------------------
       1. GLOBAL RESETS & TYPOGRAPHY
       ------------------------------------------------------------------------ */
    .stApp {{
        background-color: {DESIGN_SYSTEM['colors']['bg_app']};
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        font-family: {DESIGN_SYSTEM['typography']['font_family']};
        -webkit-font-smoothing: antialiased;
    }}
    
    [data-testid="stSidebar"] {{ display: none; }}
    
    /* Hide Streamlit default chrome elements */
    #MainMenu, footer, header {{ visibility: hidden; }}
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
        max-width: 1400px;
    }}

    /* ------------------------------------------------------------------------
       2. APP SHELL & PRODUCT HEADER
       ------------------------------------------------------------------------ */
    .aerchain-app-header {{
        background-color: {DESIGN_SYSTEM['colors']['surface_card']};
        border: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        border-radius: {DESIGN_SYSTEM['radius']['lg']};
        padding: 16px 24px;
        margin-bottom: 16px;
    }}
    
    .aerchain-brand-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        padding-bottom: 10px;
        margin-bottom: 12px;
    }}
    
    .brand-mark {{
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .rfq-meta-line {{
        font-size: 0.82rem;
        color: {DESIGN_SYSTEM['colors']['text_secondary']};
        display: flex;
        align-items: center;
        gap: 16px;
    }}

    /* ------------------------------------------------------------------------
       3. WORKFLOW STEPPER BAR
       ------------------------------------------------------------------------ */
    .workflow-stepper-container {{
        background-color: {DESIGN_SYSTEM['colors']['surface_card']};
        border: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        border-radius: {DESIGN_SYSTEM['radius']['lg']};
        padding: 8px 16px;
        margin-bottom: 20px;
    }}

    /* ------------------------------------------------------------------------
       4. WORKSPACE SECTIONS & SURFACES
       ------------------------------------------------------------------------ */
    .aerchain-section {{
        background-color: {DESIGN_SYSTEM['colors']['surface_card']};
        border: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        border-radius: {DESIGN_SYSTEM['radius']['lg']};
        padding: 24px;
        margin-bottom: 20px;
    }}

    .section-header-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        margin: 0 0 4px 0;
        letter-spacing: -0.01em;
    }}

    .section-header-subtitle {{
        font-size: 0.82rem;
        color: {DESIGN_SYSTEM['colors']['text_secondary']};
        margin: 0 0 16px 0;
    }}

    /* ------------------------------------------------------------------------
       5. METRIC & KPI CARDS
       ------------------------------------------------------------------------ */
    .kpi-card {{
        background-color: {DESIGN_SYSTEM['colors']['surface_card']};
        border: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        border-radius: {DESIGN_SYSTEM['radius']['md']};
        padding: 16px;
        text-align: left;
    }}
    .kpi-label {{
        font-size: 0.70rem;
        font-weight: 600;
        color: {DESIGN_SYSTEM['colors']['text_muted']};
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
    }}
    .kpi-value {{
        font-size: 1.4rem;
        font-weight: 700;
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        line-height: 1.2;
    }}
    .kpi-subtext {{
        font-size: 0.75rem;
        color: {DESIGN_SYSTEM['colors']['text_secondary']};
        margin-top: 4px;
    }}

    /* ------------------------------------------------------------------------
       6. BADGES & STATUS INDICATORS
       ------------------------------------------------------------------------ */
    .badge-base {{
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: {DESIGN_SYSTEM['radius']['sm']};
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }}
    .badge-confirmed {{ background-color: {DESIGN_SYSTEM['colors']['status_success_bg']}; color: {DESIGN_SYSTEM['colors']['status_success_text']}; border: 1px solid {DESIGN_SYSTEM['colors']['status_success_border']}; }}
    .badge-normalized {{ background-color: {DESIGN_SYSTEM['colors']['status_info_bg']}; color: {DESIGN_SYSTEM['colors']['status_info_text']}; border: 1px solid {DESIGN_SYSTEM['colors']['status_info_border']}; }}
    .badge-review {{ background-color: {DESIGN_SYSTEM['colors']['status_warning_bg']}; color: {DESIGN_SYSTEM['colors']['status_warning_text']}; border: 1px solid {DESIGN_SYSTEM['colors']['status_warning_border']}; }}
    .badge-danger {{ background-color: {DESIGN_SYSTEM['colors']['status_danger_bg']}; color: {DESIGN_SYSTEM['colors']['status_danger_text']}; border: 1px solid {DESIGN_SYSTEM['colors']['status_danger_border']}; }}
    .badge-neutral {{ background-color: #F1F5F9; color: #334155; border: 1px solid #CBD5E1; }}

    /* ------------------------------------------------------------------------
       7. BUTTONS & FORM INPUTS
       ------------------------------------------------------------------------ */
    .stButton button[kind="primary"] {{
        background-color: {DESIGN_SYSTEM['colors']['accent_primary']} !important;
        color: #FFFFFF !important;
        border: 1px solid {DESIGN_SYSTEM['colors']['accent_primary']} !important;
        font-weight: 500 !important;
        border-radius: {DESIGN_SYSTEM['radius']['md']} !important;
        padding: 6px 16px !important;
        font-size: 0.85rem !important;
    }}
    .stButton button[kind="primary"]:hover {{
        background-color: {DESIGN_SYSTEM['colors']['accent_hover']} !important;
    }}
    .stButton button[kind="secondary"] {{
        background-color: #FFFFFF !important;
        color: {DESIGN_SYSTEM['colors']['text_primary']} !important;
        border: 1px solid {DESIGN_SYSTEM['colors']['border_strong']} !important;
        font-weight: 500 !important;
        border-radius: {DESIGN_SYSTEM['radius']['md']} !important;
        padding: 6px 16px !important;
        font-size: 0.85rem !important;
    }}
    .stButton button[kind="secondary"]:hover {{
        background-color: #F1F5F9 !important;
    }}

    /* Decision basis column styles */
    .decision-list-item {{
        font-size: 0.83rem;
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        padding: 6px 0;
        border-bottom: 1px dashed {DESIGN_SYSTEM['colors']['border_subtle']};
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .section-divider {{
        height: 1px;
        background-color: {DESIGN_SYSTEM['colors']['border_subtle']};
        margin: 20px 0;
    }}
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# VERTEX AI CLIENT INITIALIZATION
# =============================================================================
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

def invalidate_analysis_snapshot():
    st.session_state.last_analysis_result = None
    st.session_state.last_analysis_query = None
    st.session_state.last_analysis_context = None

def compute_dataset_fingerprint():
    rfq_str = json.dumps(st.session_state.rfq_data["line_items"], sort_keys=True)
    matrix_str = st.session_state.master_matrix.to_json()
    demo_str = str(st.session_state.demo_mode)
    uploaded_str = ",".join(sorted(list(st.session_state.uploaded_suppliers)))
    combined = f"{rfq_str}|{matrix_str}|{demo_str}|{uploaded_str}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

# =============================================================================
# UNTRUNCATED NATIVE DOCUMENT EXTRACTION HELPERS
# =============================================================================
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

# =============================================================================
# CANONICAL DATASETS & INITIAL ARCHETYPES
# =============================================================================
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

def compute_rfq_fingerprint(items_list):
    raw = json.dumps(items_list, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

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
            "Apex_Source_Ref": "Demo Baseline",
            
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
            "3-Year Reported Defect Rate",
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

# =============================================================================
# PERSISTENT WORKFLOW STATE & DATA SYNCHRONIZATION ENGINE
# =============================================================================
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

if "supplier_quote_fingerprints" not in st.session_state:
    st.session_state.supplier_quote_fingerprints = {}

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
    canon_items = get_canonical_30_items()
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
        "line_items": canon_items,
        "rfq_fingerprint": compute_rfq_fingerprint(canon_items),
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

# =============================================================================
# DYNAMIC RULE-BASED QUALIFICATION & SPEND ENGINE
# =============================================================================
def calculate_deterministic_spend_engine(df, quest_df, uploaded_suppliers_set, is_demo_mode):
    is_baseline_valid = rfq_matches_demo_baseline()
    current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "")
    
    if is_demo_mode:
        if is_baseline_valid:
            active_suppliers = SUPPLIERS
        else:
            active_suppliers = [s for s in SUPPLIERS if s in uploaded_suppliers_set]
    else:
        active_suppliers = [s for s in SUPPLIERS if s in uploaded_suppliers_set]

    qualification_status = {}
    for sname in SUPPLIERS:
        if sname in quest_df.columns:
            iso_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "ISO 9001 Certification Attached?", sname].values
            defect_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "3-Year Reported Defect Rate", sname].values
            
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
    stale_quote_suppliers = set()
    exception_line_numbers = set()
    dynamic_issue_descriptions = []

    for sname in uploaded_suppliers_set:
        quote_fp = st.session_state.supplier_quote_fingerprints.get(sname, "")
        if quote_fp and quote_fp != current_rfq_fp:
            stale_quote_suppliers.add(sname)
            dynamic_issue_descriptions.append(f"**{sname}:** Quote predates updated RFQ requirements (STALE — REVALIDATION REQUIRED).")

    for sname in active_suppliers:
        meta = SUPPLIER_MAP[sname]
        norm_col = meta["norm_col"]
        status_col = meta["status_col"]
        
        if norm_col not in df.columns:
            continue
            
        is_stale = sname in stale_quote_suppliers
        
        if is_stale:
            usable_rows = pd.DataFrame()
            lines_quoted = 0
            has_missing = True
            has_review = False
            total_spend = 0.0
            is_complete = False
        else:
            usable_rows = df[
                df[norm_col].notnull() & 
                df[status_col].isin(["CONFIRMED", "NORMALIZED"])
            ]
            lines_quoted = len(df[df[norm_col].notnull()])
            has_missing = (df[status_col] == "MISSING").any()
            has_review = (df[status_col] == "REVIEW REQUIRED").any()
            total_spend = (usable_rows[norm_col] * usable_rows["Quantity"]).sum()
            is_complete = (lines_quoted == len(df)) and (not has_missing) and (not has_review)

        is_qual = qualification_status.get(sname, {}).get("qualified", True)
        
        unquoted_items = []
        review_items = []
        if not is_stale:
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
            "is_stale": is_stale,
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
        if v["qualified"] and v["is_complete"] and not v["is_stale"]
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
        if v["qualified"] and not v["is_stale"]
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

# =============================================================================
# REFINED ENTERPRISE APP SHELL HEADER
# =============================================================================
status_badge_class = "badge-neutral"
if st.session_state.rfq_status == "Published":
    status_badge_class = "badge-confirmed"
elif "Draft" in st.session_state.rfq_status:
    status_badge_class = "badge-review"

st.markdown(f"""
<div class="aerchain-app-header">
    <div class="aerchain-brand-row">
        <div class="brand-mark">
            <span style="color: {DESIGN_SYSTEM['colors']['accent_primary']}; font-size: 1.1rem;">❖</span> AERCHAIN &nbsp;·&nbsp; <span style="font-weight: 500; color: {DESIGN_SYSTEM['colors']['text_secondary']};">Procurement Intelligence Workspace</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
            <span class="badge-base {status_badge_class}">{st.session_state.rfq_status}</span>
            <span class="badge-base badge-neutral">{'Demo Mode' if st.session_state.demo_mode else 'Strict Live Mode'}</span>
        </div>
    </div>
    <div style="display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 12px;">
        <div>
            <h1 style="margin: 0; font-size: 1.35rem; font-weight: 700; color: {DESIGN_SYSTEM['colors']['text_primary']}; letter-spacing: -0.01em;">
                {st.session_state.rfq_data['title']}
            </h1>
            <div class="rfq-meta-line" style="margin-top: 6px;">
                <span><strong>RFQ ID:</strong> RFQ-2026-PKG-001</span>
                <span>•</span>
                <span><strong>Scope:</strong> {len(st.session_state.rfq_data['line_items'])} Line Items</span>
                <span>•</span>
                <span><strong>Locations:</strong> {st.session_state.rfq_data['delivery_locations']}</span>
                <span>•</span>
                <span><strong>Deadline:</strong> {st.session_state.rfq_data['response_deadline']}</span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation Guard Notice
if st.session_state.pending_extraction:
    pending_vendor = st.session_state.pending_extraction.get("supplier", "Vendor")
    st.warning(f"⚠️ **Pending Extraction Review:** Extracted quote data for **{pending_vendor}** has not yet been added to the comparison matrix. Please apply or discard the extracted quote below before proceeding.")

# =============================================================================
# REFINED WORKFLOW STEPPER BAR
# =============================================================================
stages = [
    ("Create RFQ", "01 Requirements", True),
    ("Supplier Responses", "02 Responses", st.session_state.responses_unlocked),
    ("Compare Bids", "03 Compare", st.session_state.compare_unlocked and not st.session_state.pending_extraction),
    ("Analyze & Decide", "04 Analyze", st.session_state.analyze_unlocked and not st.session_state.pending_extraction)
]
cur_idx = [s[0] for s in stages].index(st.session_state.stage)

st.markdown("<div class='workflow-stepper-container'>", unsafe_allow_html=True)
step_cols = st.columns(4)
for idx, (stage_key, stage_label, is_unlocked) in enumerate(stages):
    if idx < cur_idx:
        btn_label = f"✓ {stage_label}"
        b_type = "secondary"
    elif idx == cur_idx:
        btn_label = f"● {stage_label}"
        b_type = "primary"
    else:
        btn_label = f"🔒 {stage_label}" if not is_unlocked else f"{stage_label}"
        b_type = "secondary"
        
    with step_cols[idx]:
        if st.button(btn_label, key=f"seq_step_{idx}", type=b_type, disabled=not is_unlocked, use_container_width=True):
            st.session_state.stage = stage_key
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# STAGE 1: REQUIREMENTS / CREATE RFQ
# =============================================================================
if st.session_state.stage == "Create RFQ":
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>RFQ Brief & Requirements</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Describe your sourcing scope, SKU quantities, commercial constraints and delivery specifications below.</div>", unsafe_allow_html=True)

    prompt_val = st.text_area(
        "Procurement Brief Prompt:",
        value="I need to source corrugated packaging boxes for our Bhiwandi and Hosur logistics operations. Require 30 line items across 5-ply heavy duty and 3-ply standard shipping cartons. ISO 9001 certification mandatory with Net 60 payment terms.",
        height=85,
        placeholder="Include quantities, specifications, delivery locations, timing and commercial terms if known..."
    )
    
    if st.button("Generate RFQ draft", type="primary"):
        with st.spinner("Analyzing brief · Extracting specifications · Structuring 30 SKUs..."):
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
                    st.session_state.rfq_data["rfq_fingerprint"] = compute_rfq_fingerprint(valid_items)
                    sync_rfq_to_master_matrix()
                    invalidate_analysis_snapshot()
                    st.session_state.rfq_generated = True
                    st.session_state.rfq_status = "Draft ready"
                    st.success("RFQ draft created successfully.")
                else:
                    raise ValueError("AI generated invalid RFQ line items.")
            except Exception:
                canon_items = get_canonical_30_items()
                st.session_state.rfq_data["line_items"] = canon_items
                st.session_state.rfq_data["rfq_fingerprint"] = compute_rfq_fingerprint(canon_items)
                st.session_state.rfq_data["unclear_specs"] = [
                    "Price Validity: Mandatory duration not explicitly specified in prompt (Recommended: 60 Days)",
                    "Buffer Lead Time: Volume spike buffer lead time not specified for peak season"
                ]
                sync_rfq_to_master_matrix()
                invalidate_analysis_snapshot()
                st.warning("Reverted to standard canonical RFQ draft baseline.")
                st.session_state.rfq_generated = True

    st.markdown("</div>", unsafe_allow_html=True)
    
    # Structured Extracted Requirements Summary
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>Structured Requirements Summary</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Key parameters extracted from procurement brief.</div>", unsafe_allow_html=True)
    
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Category</div><div class='kpi-value' style='font-size:1.1rem;'>{st.session_state.rfq_data['category']}</div></div>", unsafe_allow_html=True)
    with s_col2:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Delivery Destinations</div><div class='kpi-value' style='font-size:1.1rem;'>{st.session_state.rfq_data['delivery_locations']}</div></div>", unsafe_allow_html=True)
    with s_col3:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Target Payment Terms</div><div class='kpi-value' style='font-size:1.1rem;'>{st.session_state.rfq_data['payment_terms']}</div></div>", unsafe_allow_html=True)
    with s_col4:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Price Validity Benchmark</div><div class='kpi-value' style='font-size:1.1rem;'>{st.session_state.rfq_data['price_validity']}</div></div>", unsafe_allow_html=True)
    
    if st.session_state.rfq_data["unclear_specs"]:
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#B45309; margin-bottom:8px;'>NEEDS YOUR CONFIRMATION</div>", unsafe_allow_html=True)
        for spec_item in st.session_state.rfq_data["unclear_specs"]:
            st.markdown(f"<div style='font-size:0.82rem; color:#475569; padding:4px 0;'>• {spec_item}</div>", unsafe_allow_html=True)
            
    st.markdown("</div>", unsafe_allow_html=True)

    # Line Items Editor Section
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown(f"<div class='section-header-title'>Line Items ({len(st.session_state.rfq_data['line_items'])} SKUs)</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Review and edit quantities, UOMs, specifications and target delivery locations before publishing.</div>", unsafe_allow_html=True)
    
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
        
    edited_records = edited_items.to_dict(orient="records")
    st.session_state.rfq_data["line_items"] = edited_records
    st.session_state.rfq_data["rfq_fingerprint"] = compute_rfq_fingerprint(edited_records)
    sync_rfq_to_master_matrix()
    invalidate_analysis_snapshot()

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2, 1, 1])
    with f2:
        if st.button("Save draft", type="secondary", use_container_width=True):
            st.session_state.rfq_status = "Draft saved"
            st.success("Draft saved successfully.")
    with f3:
        if st.button("Publish RFQ →", type="primary", disabled=has_invalid_qty, use_container_width=True):
            st.session_state.rfq_status = "Published"
            st.session_state.responses_unlocked = True
            st.session_state.stage = "Supplier Responses"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# STAGE 2: SUPPLIER RESPONSES & EXTRACTION
# =============================================================================
elif st.session_state.stage == "Supplier Responses":
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>Supplier Response Management</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Track supplier response status, extract quotation line items, and review verification exceptions.</div>", unsafe_allow_html=True)

    demo_c1, demo_c2 = st.columns([3, 1])
    with demo_c1:
        if st.session_state.demo_mode:
            st.info("💡 **Demo Mode Active:** Preloaded baseline quotes are included for demonstration. Uploaded supplier responses replace baseline values for validated lines.")
        else:
            st.success("🔒 **Strict Live Mode:** Displaying uploaded supplier responses only.")
    with demo_c2:
        new_demo_mode = st.toggle("Include demo baseline data", value=st.session_state.demo_mode)
        if new_demo_mode != st.session_state.demo_mode:
            st.session_state.demo_mode = new_demo_mode
            invalidate_analysis_snapshot()
            st.rerun()

    if st.session_state.demo_mode and not rfq_matches_demo_baseline():
        st.warning("⚠️ **Demo Baseline Mismatch (Reference Only):** Baseline supplier quotes were generated for the original RFQ. Because requirements were modified, baseline pricing is kept for visual reference only and excluded from sourcing calculations. Please upload supplier responses for updated requirements.")

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    responses_rcvd_count = len(st.session_state.uploaded_suppliers)
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Uploaded Responses</div><div class='kpi-value'>{responses_rcvd_count} / {len(SUPPLIERS)}</div><div class='kpi-subtext'>Supplier submissions</div></div>", unsafe_allow_html=True)
    with s2:
        if st.session_state.demo_mode:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Demo Baseline Quotes</div><div class='kpi-value'>5 / 5</div><div class='kpi-subtext'>Preloaded baselines</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Complete Quotes</div><div class='kpi-value'>{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])} / {len(calc['active_suppliers'])}</div><div class='kpi-subtext'>100% coverage</div></div>", unsafe_allow_html=True)
    with s3:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Suppliers</div><div class='kpi-value'>{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}</div><div class='kpi-subtext'>Passed compliance</div></div>", unsafe_allow_html=True)
    with s4:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Exception Lines</div><div class='kpi-value'>{calc['total_line_exceptions']}</div><div class='kpi-subtext'>Require verification</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Supplier Response Status Inbox</div>", unsafe_allow_html=True)
    
    inbox_rows = []
    for sname in SUPPLIERS:
        is_active = sname in calc["active_suppliers"]
        info = calc["supplier_totals"].get(sname, {"lines_quoted": 0, "total_lines": len(st.session_state.master_matrix), "is_complete": False, "is_stale": False})
        q_info = calc["qualification_status"].get(sname, {"qualified": False})
        
        coverage = f"{info['lines_quoted']} / {info['total_lines']} lines" if is_active else "Excluded (Reference Only)"
        qual_str = "Qualified" if q_info["qualified"] else "Disqualified"
        
        if info.get("is_stale"):
            data_qual = "STALE — REVALIDATION REQUIRED"
        else:
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
    st.markdown("</div>", unsafe_allow_html=True)

    # Document Extraction Workspace Section
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>Add Supplier Quotation Document</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Upload quotation files to automatically extract and normalize line item prices into the comparison matrix.</div>", unsafe_allow_html=True)
    
    up_col1, up_col2 = st.columns([2.5, 1.5])
    with up_col1:
        uploaded_file = st.file_uploader(
            "Drop supplier quotation document (PDF, XLSX, DOCX, JPG, PNG, TXT)",
            type=["pdf", "xlsx", "docx", "png", "jpg", "txt"],
            label_visibility="collapsed"
        )
    with up_col2:
        supplier_target = st.selectbox("Target Supplier:", SUPPLIERS)
        if uploaded_file and st.button("Extract quote data", type="primary", use_container_width=True):
            file_bytes = uploaded_file.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            
            if file_hash in st.session_state.processed_file_hashes:
                st.warning("⚠ Duplicate file detected. This document has already been processed and applied.")
            else:
                with st.spinner(f"Extracting and normalizing quotation line items for {supplier_target}..."):
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
                                 "quoted_uom": "pcs or 100 pcs or box or carton or kg",
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

    if st.session_state.pending_extraction:
        p_data = st.session_state.pending_extraction["parsed"]
        sname = st.session_state.pending_extraction['supplier']
        has_mismatch = st.session_state.pending_extraction.get('has_mismatch', False)
        detected_vendor = st.session_state.pending_extraction.get('detected_vendor', '')
        
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:1.0rem; font-weight:600; color:#0F172A;'>Review Extracted Quote: {sname}</div>", unsafe_allow_html=True)
        st.caption(f"Source Document: `{st.session_state.pending_extraction['file_name']}` &nbsp;·&nbsp; Auditable AI Extraction Workspace")
        
        confirm_override = True
        if has_mismatch:
            st.warning(f"⚠ **Supplier Identity Mismatch:** Selected target vendor is **{sname}**, but document header indicates **'{detected_vendor}'**.")
            confirm_override = st.checkbox(f"☑ I confirm this document belongs to **{sname}**", value=False)

        valid_rfq_map = {it["Line #"]: it for it in st.session_state.rfq_data["line_items"]}
        seen_lines = set()
        
        review_table = []
        matched_count = 0
        rejected_count = 0
        validated_count = 0
        needs_review_count = 0

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
                
            raw_src_ref = item.get("source_reference")
            src_ref = raw_src_ref if (raw_src_ref and pd.notna(raw_src_ref) and str(raw_src_ref).strip()) else "Source Reference Unavailable"
            
            is_known_currency = curr in ["INR", "USD"]
            if curr == "USD":
                fx = DEMO_FX_RATE
            else:
                fx = 1.0
                
            is_valid_line = lnum in valid_rfq_map
            is_duplicate = lnum in seen_lines
            is_valid_price = (raw_p is not None) and (raw_p > 0)
            
            req_uom = str(valid_rfq_map.get(lnum, {}).get("UOM", "pcs")).lower()
            uom_match = (req_uom == q_uom) or (req_uom in ["pc", "pcs"] and q_uom in ["pc", "pcs"])
            uom_convertible = uom_match or (q_uom in ["100 pcs", "100pcs", "box of 100 pcs"] and basis_qty == 100.0)
            
            if is_valid_line and not is_duplicate and is_valid_price:
                seen_lines.add(lnum)
                matched_count += 1
                
                if not is_known_currency:
                    norm_price = None
                    status_str = "REVIEW REQUIRED"
                    basis_desc = f"Unsupported currency ({curr}) — INR normalization unavailable"
                    needs_review_count += 1
                elif not is_valid_basis:
                    norm_price = None
                    status_str = "REVIEW REQUIRED"
                    basis_desc = f"Invalid price basis quantity ({basis_qty}) — normalization unavailable"
                    needs_review_count += 1
                elif not uom_convertible:
                    norm_price = None
                    status_str = "REVIEW REQUIRED"
                    basis_desc = f"UOM mismatch ({q_uom} vs requested {req_uom}) — conversion factor unavailable"
                    needs_review_count += 1
                elif conf_num < 90.0:
                    norm_price = round((raw_p * fx) / basis_qty, 2)
                    status_str = "REVIEW REQUIRED"
                    basis_desc = f"Low extraction confidence ({conf_num:.0f}%) — verification required"
                    needs_review_count += 1
                else:
                    norm_price = round((raw_p * fx) / basis_qty, 2)
                    is_normalized = (curr == "USD") or (basis_qty != 1.0)
                    status_str = "NORMALIZED" if is_normalized else "CONFIRMED"
                    basis_desc = f"{'USD → INR' if curr == 'USD' else 'Direct INR'} (/{basis_qty:g} → /pc)" if is_normalized else "Direct INR"
                    validated_count += 1
                    
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
                "Extraction Confidence": conf_str,
                "Validation Status": status_str,
                "Response Source": "Supplier Submitted"
            })
        
        extracted_total = len(review_table)
        st.dataframe(pd.DataFrame(review_table), use_container_width=True, height=220, hide_index=True)
        st.caption(f"Extraction Summary: **{extracted_total} extracted** · **{validated_count} validated** · **{needs_review_count} require review** · **{rejected_count} rejected**")
        st.caption("ℹ Review required values can be added to the comparison matrix for visibility but are excluded from sourcing calculations until validated.")
        
        rev_col1, rev_col2 = st.columns([1.5, 1])
        with rev_col1:
            apply_btn_label = f"Add {matched_count} extracted values to comparison"
            if st.button(apply_btn_label, type="primary", disabled=(matched_count == 0 or not confirm_override), use_container_width=True):
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
                        conf_val = row_entry["Extraction Confidence"]
                        src_val = row_entry["Source Reference"]
                        
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, norm_col] = norm_val
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, orig_col] = orig_rep
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, status_col] = status_val
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, conf_col] = conf_val
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, source_col] = src_val
                        
                st.session_state.uploaded_suppliers.add(sname)
                st.session_state.supplier_quote_fingerprints[sname] = st.session_state.rfq_data.get("rfq_fingerprint", "")
                st.session_state.processed_file_hashes.add(st.session_state.pending_extraction["file_hash"])
                st.session_state.uploaded_docs_log.append({
                    "file": st.session_state.pending_extraction["file_name"],
                    "supplier": sname,
                    "summary": f"Added {matched_count} extracted line items ({validated_count} validated, {needs_review_count} review required)."
                })
                st.session_state.pending_extraction = None
                invalidate_analysis_snapshot()
                st.success(f"✓ Added {matched_count} extracted values for {sname} to comparison matrix ({validated_count} validated · {needs_review_count} require review).")
                st.rerun()
        with rev_col2:
            if st.button("Discard extraction", type="secondary", use_container_width=True):
                st.session_state.pending_extraction = None
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← Back to Requirements", type="secondary"):
            st.session_state.stage = "Create RFQ"
            st.rerun()
    with b2:
        if st.button("Continue to Compare Quotes →", type="primary", disabled=bool(st.session_state.pending_extraction)):
            st.session_state.compare_unlocked = True
            st.session_state.stage = "Compare Bids"
            st.rerun()

# =============================================================================
# STAGE 3: COMPARE QUOTES & COMPLIANCE
# =============================================================================
elif st.session_state.stage == "Compare Bids":
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>Supplier Pricing & Qualification Matrix</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Compare normalized prices, quote coverage and qualification status. Values marked Review Required or Stale are excluded from sourcing calculations.</div>", unsafe_allow_html=True)

    demo_c1, demo_c2 = st.columns([3, 1])
    with demo_c1:
        if st.session_state.demo_mode:
            st.info("💡 **Demo Mode Active:** Preloaded baseline quotes are included for demonstration. Uploaded supplier responses replace baseline values for validated lines.")
        else:
            st.success("🔒 **Strict Live Mode:** Displaying uploaded supplier responses only.")
    with demo_c2:
        new_demo_mode = st.toggle("Include demo baseline data", value=st.session_state.demo_mode)
        if new_demo_mode != st.session_state.demo_mode:
            st.session_state.demo_mode = new_demo_mode
            invalidate_analysis_snapshot()
            st.rerun()

    if st.session_state.demo_mode and not rfq_matches_demo_baseline():
        st.warning("⚠️ **Demo Baseline Mismatch (Reference Only):** Baseline supplier quotes were generated for the original RFQ. Because requirements were modified, baseline pricing is kept for visual reference only and excluded from sourcing calculations. Please upload supplier responses for updated requirements.")

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    responses_rcvd_count = len(st.session_state.uploaded_suppliers)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Uploaded Responses</div><div class='kpi-value'>{responses_rcvd_count} / {len(SUPPLIERS)}</div><div class='kpi-subtext'>Supplier submissions</div></div>", unsafe_allow_html=True)
    with c2:
        if st.session_state.demo_mode:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Demo Baseline Quotes</div><div class='kpi-value'>5 / 5</div><div class='kpi-subtext'>Preloaded baselines</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Complete Quotes</div><div class='kpi-value'>{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])}</div><div class='kpi-subtext'>100% coverage</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Vendors</div><div class='kpi-value'>{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}</div><div class='kpi-subtext'>Passed compliance</div></div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Exception Lines</div><div class='kpi-value'>{calc['total_line_exceptions']}</div><div class='kpi-subtext'>Require verification</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Supplier Portfolio Summary</div>", unsafe_allow_html=True)

    summary_rows = []
    for sname in calc["active_suppliers"]:
        info = calc["supplier_totals"][sname]
        q_info = calc["qualification_status"][sname]
        
        if info.get("is_stale"):
            spend_str = "Stale Quote (Revalidation Required)"
            dq_str = "STALE — REVALIDATION REQUIRED"
        else:
            spend_str = f"₹{info['total_spend']:,.0f}" if info['is_complete'] else (f"Partial (₹{info['total_spend']:,.0f})" if info['usable_lines'] > 0 else "No Usable Quotes")
            dq_str = "Complete" if info['is_complete'] else ("Review Required" if info['has_review'] else f"Incomplete ({info['total_lines'] - info['lines_quoted']} unquoted)")

        summary_rows.append({
            "Supplier": sname,
            "Response Source": "Supplier Submitted" if sname in st.session_state.uploaded_suppliers else "Demo Baseline",
            "Coverage": f"{info['lines_quoted']} / {info['total_lines']} lines",
            "Qualification": "Qualified" if q_info['qualified'] else "Disqualified",
            "Data Quality": dq_str,
            "Usable Quoted Spend": spend_str
        })
        
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    if calc["dynamic_issue_descriptions"]:
        with st.expander(f"Issues requiring attention · {calc['total_line_exceptions']} lines affected"):
            for issue_desc in calc["dynamic_issue_descriptions"]:
                st.markdown(f"* {issue_desc}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Matrix Section
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    tab_comp1, tab_comp2 = st.tabs(["Price comparison matrix", "Qualification checks"])
    
    with tab_comp1:
        m_col1, m_col2 = st.columns([2, 1])
        with m_col1:
            st.session_state.exception_filter = st.selectbox(
                "Filter matrix view:",
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
            q_lbl = "Qualified" if calc["qualification_status"].get(sname, {}).get("qualified", False) else "Disqualified"
            prov_lbl = "Submitted" if sname in st.session_state.uploaded_suppliers else "Demo Baseline"
            col_rename_map[SUPPLIER_MAP[sname]["norm_col"]] = f"{sname}\n({q_lbl} · {prov_lbl})"
        matrix_display = matrix_display.rename(columns=col_rename_map)
        
        if st.session_state.exception_filter == "Quoted lines with exceptions":
            matrix_display = matrix_display[matrix_display["Line #"].isin(calc["exception_line_numbers"])]

        for sname in calc["active_suppliers"]:
            q_lbl = "Qualified" if calc["qualification_status"].get(sname, {}).get("qualified", False) else "Disqualified"
            prov_lbl = "Submitted" if sname in st.session_state.uploaded_suppliers else "Demo Baseline"
            col_key = f"{sname}\n({q_lbl} · {prov_lbl})"
            if col_key in matrix_display.columns:
                matrix_display[col_key] = matrix_display[col_key].astype(str).replace(["nan", "None", "<NA>"], "—")

        def style_matrix_cells(row):
            styles = [''] * len(row)
            
            qual_col_indices = []
            for col_idx in range(4, len(row)):
                sname = calc["active_suppliers"][col_idx - 4]
                info = calc["supplier_totals"].get(sname, {})
                if info.get("qualified", False) and not info.get("is_stale", False):
                    qual_col_indices.append(col_idx)

            valid_prices = {}
            for col_idx in range(4, len(row)):
                val = row.iloc[col_idx]
                sname = calc["active_suppliers"][col_idx - 4]
                status = str(st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == row["Line #"], SUPPLIER_MAP[sname]["status_col"]].values[0]).upper()
                
                if status == "REVIEW REQUIRED":
                    styles[col_idx] = 'background-color: #FFFBEB; color: #B45309;'
                    continue
                    
                if val != "—" and col_idx in qual_col_indices:
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
        <div style="font-size: 0.78rem; color: #64748B; margin-top: 6px;">
            <strong>Legend:</strong> &nbsp;
            <span style="background-color: #F0FDF4; color: #166534; padding: 2px 6px; border-radius: 4px; border: 1px solid #BBF7D0;">Lowest usable qualified price — price comparison only, not an award recommendation</span> &nbsp;
            <span style="background-color: #FFFBEB; color: #B45309; padding: 2px 6px; border-radius: 4px; border: 1px solid #FEF08A;">Review required (excluded from sourcing)</span> &nbsp;
            <span>— Unquoted / Missing</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Normalization: USD → INR at ₹83.50/USD · Quoted prices normalized to requested UOM. Review required values are displayed for visibility but excluded from sourcing calculations.")

    with tab_comp2:
        st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:4px;'>Qualification Checks Evaluation</div>", unsafe_allow_html=True)
        st.caption("Mandatory Criteria: ISO 9001 certification required AND 3-year reported defect rate < 0.5%")
        
        qual_summary = []
        for sname in calc["active_suppliers"]:
            q_info = calc["qualification_status"][sname]
            qual_summary.append({
                "Supplier": sname,
                "ISO 9001": q_info["iso"],
                "3-Year Defect Rate": q_info["defect"],
                "Qualification": "Qualified" if q_info["qualified"] else "Disqualified",
                "Reason / Evaluation": q_info["reason"]
            })
        st.dataframe(pd.DataFrame(qual_summary), use_container_width=True, hide_index=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
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

# =============================================================================
# STAGE 4: SCENARIO ANALYSIS & EXECUTIVE BRIEFING
# =============================================================================
elif st.session_state.stage == "Analyze & Decide":
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>Sourcing Scenario Analysis</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Evaluate sourcing scenarios using available supplier quote data. Spend calculations follow defined sourcing rules; AI interprets trade-offs and data gaps.</div>", unsafe_allow_html=True)

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    current_dataset_fp = compute_dataset_fingerprint()

    if st.session_state.last_analysis_context:
        saved_ctx = st.session_state.last_analysis_context
        is_stale = saved_ctx.get("dataset_hash") != current_dataset_fp
        if is_stale:
            st.warning("⚠️ **Dataset Modified Since Last Analysis:** RFQ requirements or supplier quote availability have changed since this analysis was generated. Click 'Run analysis' below to refresh results.")

    st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#475569; margin-bottom:8px;'>SUGGESTED ANALYSIS ACTIONS</div>", unsafe_allow_html=True)
    q_col1, q_col2, q_col3 = st.columns(3)
    prompt_choice = None
    if q_col1.button("Lowest qualified split", type="secondary", use_container_width=True):
        prompt_choice = "What happens if we split the award across qualified suppliers based on lowest unit price?"
    if q_col2.button("Supplier eligibility", type="secondary", use_container_width=True):
        prompt_choice = "Why are certain suppliers excluded from full award scenarios?"
    if q_col3.button("Landed-cost gaps", type="secondary", use_container_width=True):
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
                  * Price Delta vs Lowest Complete Qualified Quote: ₹{abs(calc['price_diff']):,.0f} {delta_direction} ({calc['price_diff_pct']}%)
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
                    
                    st.session_state.last_analysis_query = user_query
                    st.session_state.last_analysis_result = parsed_ans
                    st.session_state.last_analysis_context = {
                        "timestamp": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
                        "dataset_hash": current_dataset_fp,
                        "demo_mode": st.session_state.demo_mode,
                        "active_count": len(calc["active_suppliers"]),
                        "line_count": len(st.session_state.rfq_data["line_items"]),
                        "qual_count": calc["total_qualified_suppliers"],
                        "disqual_count": calc["total_disqualified_suppliers"],
                        "split_spend": calc["split_spend"],
                        "best_single_spend": calc["best_single_spend"],
                        "price_diff": calc["price_diff"],
                        "price_diff_pct": calc["price_diff_pct"],
                        "unassigned_count": calc["unassigned_count"],
                        "exception_lines": calc["total_line_exceptions"]
                    }

                except Exception:
                    st.error("Scenario evaluation failed. Please refine query.")

    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.last_analysis_result:
        parsed_ans = st.session_state.last_analysis_result
        active_query = st.session_state.last_analysis_query
        
        ctx = st.session_state.last_analysis_context or {
            "timestamp": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
            "dataset_hash": current_dataset_fp,
            "demo_mode": st.session_state.demo_mode,
            "active_count": len(calc["active_suppliers"]),
            "line_count": len(st.session_state.rfq_data["line_items"]),
            "qual_count": calc["total_qualified_suppliers"],
            "disqual_count": calc["total_disqualified_suppliers"],
            "split_spend": calc["split_spend"],
            "best_single_spend": calc["best_single_spend"],
            "price_diff": calc["price_diff"],
            "price_diff_pct": calc["price_diff_pct"],
            "unassigned_count": calc["unassigned_count"],
            "exception_lines": calc["total_line_exceptions"]
        }
        
        calc_provenance_str = "baseline + submitted supplier data · Demo Mode" if ctx["demo_mode"] else "submitted supplier data only · Strict Live Mode"
        
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Executive Briefing</div>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='margin: 8px 0 16px 0; font-size: 1.25rem; font-weight: 600; color: #0F172A;'>{parsed_ans.get('headline_answer', '')}</h2>", unsafe_allow_html=True)
        st.caption(f"Generated: **{ctx.get('timestamp', 'Recent')}** · Dataset: {calc_provenance_str} · {ctx['active_count']} active suppliers · {ctx['line_count']} RFQ lines · Price-only basis")
        
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        q_lower = active_query.lower()

        if "landed" in q_lower or "gst" in q_lower or "freight" in q_lower:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>GST Rates</div><div class='kpi-value'>Missing</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Freight Costs</div><div class='kpi-value'>Missing</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Suppliers Affected</div><div class='kpi-value'>{ctx['active_count']} Vendors</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Landed Basis</div><div class='kpi-value'>Unavailable</div></div>", unsafe_allow_html=True)
                
        elif "eligib" in q_lower or "exclude" in q_lower or "qualif" in q_lower:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Vendors</div><div class='kpi-value'>{ctx['qual_count']} / {ctx['active_count']}</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Disqualified Vendors</div><div class='kpi-value'>{ctx['disqual_count']}</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Complete Quotes</div><div class='kpi-value'>{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])}</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Exception Lines</div><div class='kpi-value'>{ctx['exception_lines']}</div></div>", unsafe_allow_html=True)
                
        elif "capacity" in q_lower or "volume" in q_lower:
            rfq_uoms = set(it["UOM"] for it in st.session_state.rfq_data["line_items"])
            if len(rfq_uoms) == 1:
                single_uom = list(rfq_uoms)[0]
                total_req_units = sum(it["Quantity"] for it in st.session_state.rfq_data["line_items"])
                vol_metric_val = f"{total_req_units:,} {single_uom}"
            else:
                vol_metric_val = f"Mixed UOMs ({len(st.session_state.rfq_data['line_items'])} lines)"

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Required RFQ Volume</div><div class='kpi-value'>{vol_metric_val}</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Reporting Vendors</div><div class='kpi-value'>{ctx['active_count']} / {ctx['active_count']}</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Capacity Basis</div><div class='kpi-value'>Monthly</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Assessment Status</div><div class='kpi-value'>Inconclusive</div></div>", unsafe_allow_html=True)
            st.caption("ℹ Supplier capacity is reported monthly. RFQ fulfillment period is not specified, so capacity sufficiency cannot be conclusively determined.")

        elif "split" in q_lower or "cheapest" in q_lower or "award" in q_lower or "lowest" in q_lower:
            m1, m2, m3, m4 = st.columns(4)
            assigned_lines_count = ctx['line_count'] - ctx['unassigned_count']
            spend_label = f"₹{ctx['split_spend']:,.0f}" if ctx['unassigned_count'] == 0 else f"Partial: ₹{ctx['split_spend']:,.0f}"
            delta_label = f"₹{abs(ctx['price_diff']):,.0f} {'lower' if ctx['price_diff'] >= 0 else 'higher'}" if ctx['unassigned_count'] == 0 else "Unavailable"
            
            with m1:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Illustrative Split Spend</div><div class='kpi-value'>{spend_label}</div><div class='kpi-subtext'>{assigned_lines_count}/{ctx['line_count']} lines assigned</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Delta vs Complete Qualified</div><div class='kpi-value'>{delta_label}</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Vendors</div><div class='kpi-value'>{ctx['qual_count']} / {ctx['active_count']}</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Unassigned Lines</div><div class='kpi-value'>{ctx['unassigned_count']}</div></div>", unsafe_allow_html=True)
            
            if ctx['unassigned_count'] > 0:
                st.caption("⚠ **Note:** Price delta is unavailable because 1 or more line items have no usable qualified quote and are excluded from the illustrative split calculation.")

        else:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Active Suppliers</div><div class='kpi-value'>{ctx['active_count']} / {len(SUPPLIERS)}</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Complete Quotes</div><div class='kpi-value'>{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])}</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Suppliers</div><div class='kpi-value'>{ctx['qual_count']}</div></div>", unsafe_allow_html=True)
            with m4:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Exception Lines</div><div class='kpi-value'>{ctx['exception_lines']}</div></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if parsed_ans.get("key_drivers"):
                st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>KEY DRIVERS</div>", unsafe_allow_html=True)
                for kd in parsed_ans["key_drivers"]:
                    st.markdown(f"<div class='decision-list-item'>• {kd}</div>", unsafe_allow_html=True)
        with c2:
            if parsed_ans.get("trade_offs"):
                st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>TRADE-OFFS & CONSIDERATIONS</div>", unsafe_allow_html=True)
                for to in parsed_ans["trade_offs"]:
                    st.markdown(f"<div class='decision-list-item'>• {to}</div>", unsafe_allow_html=True)
                    
        if parsed_ans.get("data_gaps"):
            st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#475569; margin:16px 0 8px 0;'>DATA GAPS IDENTIFIED</div>", unsafe_allow_html=True)
            for dg in parsed_ans["data_gaps"]:
                st.markdown(f"<div class='decision-list-item'><span class='badge-base badge-neutral'>Data Gap</span> {dg}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Decision Basis Panel Section
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Decision Basis & Methodology</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Explicit boundaries of calculated figures and current data gaps.</div>", unsafe_allow_html=True)
        
        db_c1, db_c2 = st.columns(2)
        with db_c1:
            st.markdown("<div style='font-size:0.82rem; font-weight:600; color:#166534; margin-bottom:8px;'>INCLUDED IN CALCULATIONS</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>✓ Normalized unit prices (INR / requested UOM)</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>✓ Requested RFQ quantities</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>✓ Supplier qualification status (ISO 9001 + Defect rate)</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>✓ Quote completeness & usable lines</div>", unsafe_allow_html=True)
        with db_c2:
            st.markdown("<div style='font-size:0.82rem; font-weight:600; color:#991B1B; margin-bottom:8px;'>EXCLUDED (DATA GAPS)</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>— GST rates & numerical tax amounts</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>— Freight cost amounts (DDP vs Buyer Collect)</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>— Lead time & delivery schedule buffer</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'>— Production capacity sufficiency over fulfillment period</div>", unsafe_allow_html=True)

        if "landed" in q_lower or "gst" in q_lower:
            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-title'>Landed Cost Data-Gap Matrix</div>", unsafe_allow_html=True)
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
            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-title'>Illustrative Price-Only Split Allocation</div>", unsafe_allow_html=True)
            st.caption("Spend distribution by supplier under lowest unit price allocation — not a final award recommendation. Supplier capacity, freight, lead time and commercial terms are excluded.")
            
            st.dataframe(calc["split_allocation"], use_container_width=True, height=260, hide_index=True)
            
            fig = px.bar(
                calc["split_allocation"],
                x="Awarded Supplier",
                y="Extended Spend (INR)",
                color_discrete_sequence=[DESIGN_SYSTEM["colors"]["accent_primary"]],
                template="plotly_white",
                title="Spend Distribution by Supplier"
            )
            fig.update_layout(height=260, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # Audit Trail Export Section
    st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-title'>Audit Trail & Export</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-header-subtitle'>Export full comparison matrix, provenance sources, transformation bases, and validation audit log.</div>", unsafe_allow_html=True)

    current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "N/A")
    audit_export_rows = []
    
    for idx, row in st.session_state.master_matrix.iterrows():
        for sname in calc["active_suppliers"]:
            meta = SUPPLIER_MAP[sname]
            raw_src = row.get(meta["source_col"])
            clean_src = raw_src if (raw_src and pd.notna(raw_src) and str(raw_src).strip()) else "Source Reference Unavailable"
            
            is_submitted = sname in st.session_state.uploaded_suppliers
            quote_fp = st.session_state.supplier_quote_fingerprints.get(sname, "") if is_submitted else current_rfq_fp
            
            if is_submitted and quote_fp != current_rfq_fp:
                q_ver_status = "STALE — REVALIDATION REQUIRED"
            elif is_submitted:
                q_ver_status = "Current"
            else:
                q_ver_status = "Demo Baseline"

            audit_export_rows.append({
                "Line #": row["Line #"],
                "Description": row["Description"],
                "Quantity": row["Quantity"],
                "UOM": row["UOM"],
                "Supplier": sname,
                "Original Quote": row.get(meta["orig_col"], "—"),
                "Normalized Unit Price (INR)": row.get(meta["norm_col"], "—"),
                "Validation Status": row.get(meta["status_col"], "—"),
                "Extraction Confidence": row.get(meta["conf_col"], "—"),
                "Source Reference": clean_src,
                "Response Source": "Supplier Submitted" if is_submitted else "Demo Baseline",
                "Quote Version Status": q_ver_status,
                "RFQ Fingerprint": current_rfq_fp,
                "Qualification Status": "Qualified" if calc["qualification_status"][sname]["qualified"] else "Disqualified"
            })
            
    audit_csv_data = pd.DataFrame(audit_export_rows).to_csv(index=False).encode('utf-8')
    st.download_button("Download comparison & audit trail CSV", audit_csv_data, "RFQ_Audit_Master_Matrix.csv", "text/csv", type="secondary")
    st.markdown("</div>", unsafe_allow_html=True)
