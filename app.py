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
# CENTRALIZED DESIGN SYSTEM & CONSTANTS
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
    "Apex Packaging": {"prefix": "Apex", "orig_col": "Apex_Orig_Price", "norm_col": "Apex_Norm_INR", "status_col": "Apex_Status", "conf_col": "Apex_Confidence", "source_col": "Apex_Source_Ref", "snippet_col": "Apex_Snippet"},
    "BoxCraft Ltd": {"prefix": "BoxCraft", "orig_col": "BoxCraft_Orig_Price", "norm_col": "BoxCraft_Norm_INR", "status_col": "BoxCraft_Status", "conf_col": "BoxCraft_Confidence", "source_col": "BoxCraft_Source_Ref", "snippet_col": "BoxCraft_Snippet"},
    "CorruSeal Global": {"prefix": "CorruSeal", "orig_col": "CorruSeal_Orig_Price", "norm_col": "CorruSeal_Norm_INR", "status_col": "CorruSeal_Status", "conf_col": "CorruSeal_Confidence", "source_col": "CorruSeal_Source_Ref", "snippet_col": "CorruSeal_Snippet"},
    "National Paper Mills": {"prefix": "National", "orig_col": "National_Orig_Price", "norm_col": "National_Norm_INR", "status_col": "National_Status", "conf_col": "National_Confidence", "source_col": "National_Source_Ref", "snippet_col": "National_Snippet"},
    "PackTech Solutions": {"prefix": "PackTech", "orig_col": "PackTech_Orig_Price", "norm_col": "PackTech_Norm_INR", "status_col": "PackTech_Status", "conf_col": "PackTech_Confidence", "source_col": "PackTech_Source_Ref", "snippet_col": "PackTech_Snippet"}
}

# Dynamic Category Commercial & Qualification Defaults
CATEGORY_DEFAULTS = {
    "Packaging Materials": {
        "pay_terms": "Net 60 Days",
        "validity": "60 Days Mandatory",
        "freight": "Supplier Prepaid (DDP)",
        "iso_default": True,
        "esg_default": False,
        "fsc_visible": True,
        "fsc_default": False,
        "sample_req": True,
        "aql_visible": True,
        "aql_default": "1.0% AQL",
        "incoterm": "DDP (2020)",
        "warranty_visible": False,
        "installation_visible": False
    },
    "Office Furniture & Fixtures": {
        "pay_terms": "30% Advance, 70% Post-Installation",
        "validity": "60 Days Mandatory",
        "freight": "Supplier Prepaid (DDP)",
        "iso_default": True,
        "esg_default": False,
        "fsc_visible": False,
        "fsc_default": False,
        "sample_req": True,
        "aql_visible": False,
        "aql_default": "1.0% AQL",
        "incoterm": "DDP (2020)",
        "warranty_visible": True,
        "warranty_default": "3 Years Comprehensive",
        "installation_visible": True,
        "installation_default": "Vendor Included"
    },
    "Chemicals & Raw Materials": {
        "pay_terms": "Net 30 Days",
        "validity": "30 Days",
        "freight": "Ex-Works",
        "iso_default": True,
        "esg_default": True,
        "fsc_visible": False,
        "fsc_default": False,
        "sample_req": True,
        "aql_visible": True,
        "aql_default": "0.5% AQL",
        "incoterm": "FOB (2020)",
        "warranty_visible": False,
        "installation_visible": False
    },
    "IT Hardware & Electronics": {
        "pay_terms": "Net 45 Days",
        "validity": "90 Days",
        "freight": "Supplier Prepaid (DDP)",
        "iso_default": True,
        "esg_default": True,
        "fsc_visible": False,
        "fsc_default": False,
        "sample_req": False,
        "aql_visible": True,
        "aql_default": "0.25% AQL",
        "incoterm": "DDP (2020)",
        "warranty_visible": True,
        "warranty_default": "1 Year On-Site",
        "installation_visible": False
    },
    "Logistics & Freight Services": {
        "pay_terms": "Net 30 Days",
        "validity": "30 Days",
        "freight": "Supplier Prepaid (DDP)",
        "iso_default": False,
        "esg_default": False,
        "fsc_visible": False,
        "fsc_default": False,
        "sample_req": False,
        "aql_visible": False,
        "aql_default": "1.5% AQL",
        "incoterm": "FOB (2020)",
        "warranty_visible": False,
        "installation_visible": False
    }
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
    /* 1. GLOBAL RESETS & TYPOGRAPHY */
    .stApp {{
        background-color: {DESIGN_SYSTEM['colors']['bg_app']};
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        font-family: {DESIGN_SYSTEM['typography']['font_family']};
        -webkit-font-smoothing: antialiased;
    }}
    
    [data-testid="stSidebar"] {{ display: none; }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
        max-width: 1400px;
    }}

    /* 2. APP SHELL & PRODUCT HEADER */
    .aerchain-app-header {{
        background-color: transparent;
        border-bottom: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        padding: 8px 0 16px 0;
        margin-bottom: 16px;
    }}
    
    .aerchain-brand-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 8px;
        margin-bottom: 8px;
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

    /* 3. WORKFLOW STEPPER BAR */
    .workflow-stepper-container {{
        background-color: transparent;
        padding: 0;
        margin-bottom: 24px;
        border-bottom: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        padding-bottom: 16px;
    }}

    /* 4. WORKSPACE SECTIONS */
    .aerchain-section {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        padding-bottom: 20px;
        margin-bottom: 24px;
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

    /* 5. METRIC & KPI CARDS (EQUAL HEIGHT UNIFORM GRID) */
    .kpi-card {{
        background-color: {DESIGN_SYSTEM['colors']['surface_card']};
        border: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        border-radius: {DESIGN_SYSTEM['radius']['md']};
        padding: 16px;
        text-align: left;
        min-height: 96px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
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
        font-size: 1.3rem;
        font-weight: 700;
        color: {DESIGN_SYSTEM['colors']['text_primary']};
        line-height: 1.2;
    }}
    .kpi-subtext {{
        font-size: 0.75rem;
        color: {DESIGN_SYSTEM['colors']['text_secondary']};
        margin-top: 4px;
    }}

    /* 6. BADGES */
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

    /* 7. BUTTONS & INPUTS */
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

# Scroll to top JavaScript injection helper
def scroll_to_top():
    st.components.v1.html(
        """
        <script>
            window.parent.scrollTo({top: 0, behavior: 'instant'});
        </script>
        """,
        height=0
    )

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
    if st.session_state.rfq_data is None:
        return "empty"
        
    rfq_meta = {
        "title": st.session_state.rfq_data.get("title"),
        "category": st.session_state.rfq_data.get("category"),
        "scope": st.session_state.rfq_data.get("scope"),
        "delivery_locations": st.session_state.rfq_data.get("delivery_locations"),
        "payment_terms": st.session_state.rfq_data.get("payment_terms"),
        "price_validity": st.session_state.rfq_data.get("price_validity"),
        "freight_terms": st.session_state.rfq_data.get("freight_terms"),
        "iso_mandatory": st.session_state.rfq_data.get("iso_mandatory"),
        "fsc_mandatory": st.session_state.rfq_data.get("fsc_mandatory"),
        "esg_mandatory": st.session_state.rfq_data.get("esg_mandatory"),
        "min_capacity": st.session_state.rfq_data.get("min_capacity"),
        "target_otd": st.session_state.rfq_data.get("target_otd"),
        "defect_limit": st.session_state.rfq_data.get("defect_limit"),
        "response_deadline": st.session_state.rfq_data.get("response_deadline"),
        "line_items": st.session_state.rfq_data.get("line_items")
    }
    rfq_str = json.dumps(rfq_meta, sort_keys=True)
    matrix_str = st.session_state.master_matrix.to_json() if st.session_state.master_matrix is not None else ""
    quest_str = st.session_state.questionnaire_matrix.to_json() if st.session_state.questionnaire_matrix is not None else ""
    demo_str = str(st.session_state.demo_mode)
    uploaded_str = ",".join(sorted(list(st.session_state.uploaded_suppliers)))
    combined = f"{rfq_str}|{matrix_str}|{quest_str}|{demo_str}|{uploaded_str}"
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
        ("Regular Slotted Carton", "5-ply, 18x12x10\", 180 GSM Kraft", 4000, "pcs", "Bhiwandi Warehouse", 28.50),
        ("Regular Slotted Carton", "5-ply, 20x14x12\", 180 GSM Kraft", 3500, "pcs", "Bhiwandi Warehouse", 32.00),
        ("Regular Slotted Carton", "3-ply, 12x10x8\", 150 GSM Kraft", 5000, "pcs", "Bhiwandi Warehouse", 18.00),
        ("Regular Slotted Carton", "3-ply, 14x10x6\", 150 GSM Kraft", 4500, "pcs", "Bhiwandi Warehouse", 21.50),
        ("Heavy Duty Shipping Master Box", "5-ply, 24x18x18\", 200 GSM Kraft", 2500, "pcs", "Hosur Facility", 45.00),
        ("Heavy Duty Shipping Master Box", "5-ply, 28x20x20\", 200 GSM Kraft", 2000, "pcs", "Hosur Facility", 52.00),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 10x8x4\", 150 GSM White Kraft", 6000, "pcs", "Bhiwandi Warehouse", 24.00),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 12x9x4\", 150 GSM White Kraft", 5500, "pcs", "Bhiwandi Warehouse", 27.50),
        ("Corrugated Partition Tray", "3-ply, 12-Grid Insert, 18x12\", 120 GSM", 8000, "pcs", "Hosur Facility", 14.00),
        ("Corrugated Partition Tray", "3-ply, 24-Grid Insert, 20x14\", 120 GSM", 7500, "pcs", "Hosur Facility", 18.50),
        ("Die-Cut Self-Locking Box", "3-ply, B-Flute, 8x6x4\", 150 GSM", 6500, "pcs", "Bhiwandi Warehouse", 16.50),
        ("Die-Cut Self-Locking Box", "3-ply, B-Flute, 12x8x5\", 150 GSM", 6000, "pcs", "Bhiwandi Warehouse", 22.00),
        ("Telescopic Top/Bottom Box", "5-ply, 16x16x12\", 180 GSM Kraft", 3000, "pcs", "Hosur Facility", 38.00),
        ("Telescopic Top/Bottom Box", "5-ply, 20x20x15\", 180 GSM Kraft", 2800, "pcs", "Hosur Facility", 46.00),
        ("Heavy Duty Pallet Outer Box", "7-ply, Heavy Outer, 40x48x30\", 250 GSM", 800, "pcs", "Hosur Facility", 185.00),
        ("Regular Slotted Carton", "5-ply, 15x10x10\", 180 GSM Kraft", 4200, "pcs", "Bhiwandi Warehouse", 25.00),
        ("Regular Slotted Carton", "3-ply, 10x8x6\", 150 GSM Kraft", 7000, "pcs", "Bhiwandi Warehouse", 15.00),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 8x5x3\", 150 GSM White", 9000, "pcs", "Bhiwandi Warehouse", 19.00),
        ("Corrugated Layer Pad", "3-ply Corrugated Sheet, 18x12\", 150 GSM", 12000, "pcs", "Hosur Facility", 8.50),
        ("Corrugated Layer Pad", "5-ply Corrugated Sheet, 20x14\", 180 GSM", 10000, "pcs", "Hosur Facility", 12.00),
        ("Regular Slotted Carton", "5-ply, 22x16x14\", 180 GSM Kraft", 3200, "pcs", "Bhiwandi Warehouse", 35.00),
        ("Heavy Duty Shipping Master Box", "5-ply, 30x22x22\", 200 GSM Kraft", 1500, "pcs", "Hosur Facility", 58.00),
        ("Die-Cut Folder Box", "3-ply, C-Flute, 14x11x3\", 150 GSM", 5000, "pcs", "Bhiwandi Warehouse", 23.00),
        ("Corrugated Edge Protector", "L-Shape Heavy Corner Guard, 50x50x1000mm", 15000, "pcs", "Hosur Facility", 6.50),
        ("Regular Slotted Carton", "3-ply, 16x12x8\", 150 GSM Kraft", 5500, "pcs", "Bhiwandi Warehouse", 22.50),
        ("Heavy Duty Shipping Master Box", "5-ply, 25x15x15\", 180 GSM Kraft", 2200, "pcs", "Hosur Facility", 42.00),
        ("Corrugated Partition Tray", "3-ply, 6-Grid Insert, 15x10\", 120 GSM", 8500, "pcs", "Hosur Facility", 12.50),
        ("Regular Slotted Carton", "5-ply, 19x13x11\", 180 GSM Kraft", 3800, "pcs", "Bhiwandi Warehouse", 30.00),
        ("Custom Printed Mailer Box", "3-ply, E-Flute, 14x10x5\", 150 GSM White", 4800, "pcs", "Bhiwandi Warehouse", 29.00),
        ("Heavy Duty Pallet Outer Box", "7-ply Heavy Outer, 42x42x36\", 250 GSM", 600, "pcs", "Hosur Facility", 210.00)
    ]
    
    items = []
    for idx, (title, spec, qty, uom, loc, target_price) in enumerate(specs, start=1):
        items.append({
            "Line #": f"ITEM-{idx:03d}",
            "Description": title,
            "Quantity": qty,
            "UOM": uom,
            "Specification": spec,
            "Delivery Location": loc,
            "Target Price (INR)": target_price,
            "Est Extended Spend": round(qty * target_price, 2)
        })
    return items

def compute_rfq_fingerprint(rfq_dict_or_items):
    if rfq_dict_or_items is None:
        return "empty"
    if isinstance(rfq_dict_or_items, list):
        items_list = rfq_dict_or_items
        meta = {}
    else:
        items_list = rfq_dict_or_items.get("line_items", [])
        meta = {
            "title": rfq_dict_or_items.get("title"),
            "category": rfq_dict_or_items.get("category"),
            "scope": rfq_dict_or_items.get("scope"),
            "delivery_locations": rfq_dict_or_items.get("delivery_locations"),
            "payment_terms": rfq_dict_or_items.get("payment_terms"),
            "price_validity": rfq_dict_or_items.get("price_validity"),
            "freight_terms": rfq_dict_or_items.get("freight_terms"),
            "iso_mandatory": rfq_dict_or_items.get("iso_mandatory"),
            "fsc_mandatory": rfq_dict_or_items.get("fsc_mandatory"),
            "esg_mandatory": rfq_dict_or_items.get("esg_mandatory"),
            "min_capacity": rfq_dict_or_items.get("min_capacity"),
            "target_otd": rfq_dict_or_items.get("target_otd"),
            "defect_limit": rfq_dict_or_items.get("defect_limit"),
            "response_deadline": rfq_dict_or_items.get("response_deadline")
        }
    payload = {"meta": meta, "items": items_list}
    raw = json.dumps(payload, sort_keys=True)
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

        # Verbatim source snippets for provenance inspection
        snip_1 = f"Item #{idx:03d} ({it['Description']}): ₹{p1_orig:.2f} per unit net DDP Bhiwandi."
        snip_2 = f"SKU ITEM-{idx:03d} rate: ₹{p2_orig:.2f}/pc." if p2_orig else "Item not listed in commercial bid Schedule B."
        snip_3 = f"Part ITEM-{idx:03d}: USD ${p3_usd:.2f}/unit (converted at ₹83.50/USD baseline)."
        snip_4 = f"ITEM-{idx:03d} bulk pack rate: ₹{p4_per_100:.2f} per 100 pcs (scanned OCR image rate-card.jpg)." if idx != 20 else f"ITEM-020 rate-card OCR smudge: ₹{p4_per_100:.2f} / [ambiguous unit]."
        snip_5 = f"ITEM-{idx:03d} quote: ₹{p5_orig:.2f} / pc." if p5_orig else "Line unquoted in PackTech submission."
        
        master.append({
            "Line #": it["Line #"],
            "Description": it["Description"],
            "Specification": it["Specification"],
            "Quantity": it["Quantity"],
            "UOM": it["UOM"],
            "Delivery Location": it["Delivery Location"],
            "Target Price (INR)": it["Target Price (INR)"],
            "Est Extended Spend": it["Est Extended Spend"],
            
            "Apex_Orig_Price": f"₹{p1_orig:.2f} / pc",
            "Apex_Norm_INR": p1_orig,
            "Apex_Status": "CONFIRMED",
            "Apex_Confidence": "98%",
            "Apex_Source_Ref": "PDF Schedule A · Page 1",
            "Apex_Snippet": snip_1,
            
            "BoxCraft_Orig_Price": f"₹{p2_orig:.2f} / pc" if p2_orig else "NOT QUOTED",
            "BoxCraft_Norm_INR": p2_orig,
            "BoxCraft_Status": "CONFIRMED" if p2_orig else "MISSING",
            "BoxCraft_Confidence": "95%" if p2_orig else "0%",
            "BoxCraft_Source_Ref": "XLSX Proposal · Sheet 1, Row 14" if p2_orig else "N/A",
            "BoxCraft_Snippet": snip_2,
            
            "CorruSeal_Orig_Price": f"${p3_usd:.2f} / pc",
            "CorruSeal_Norm_INR": p3_norm,
            "CorruSeal_Status": "NORMALIZED",
            "CorruSeal_Confidence": "96%",
            "CorruSeal_Source_Ref": "DOCX Quote · Commercial Terms Page 2",
            "CorruSeal_Snippet": snip_3,
            
            "National_Orig_Price": f"₹{p4_per_100:.2f} / 100 pcs",
            "National_Norm_INR": p4_norm,
            "National_Status": "NORMALIZED" if idx != 20 else "REVIEW REQUIRED",
            "National_Confidence": "88%" if idx != 20 else "58% (Scanned Digit Ambiguity)",
            "National_Source_Ref": "rate-card-photo.jpg · Page 1",
            "National_Snippet": snip_4,
            
            "PackTech_Orig_Price": f"₹{p5_orig:.2f} / pc" if p5_orig else "UNAVAILABLE",
            "PackTech_Norm_INR": p5_orig,
            "PackTech_Status": "CONFIRMED" if p5_orig else "MISSING",
            "PackTech_Confidence": "90%" if p5_orig else "0%",
            "PackTech_Source_Ref": "TXT Commercial Email" if p5_orig else "N/A",
            "PackTech_Snippet": snip_5
        })
    return pd.DataFrame(master)

def get_questionnaire_master_dataset():
    data = {
        "Questionnaire Metric": [
            "ISO 9001 Certification Attached?",
            "FSC Certification Attached?",
            "ESG Audit Certified?",
            "3-Year Reported Defect Rate",
            "Monthly Packaging Capacity",
            "Historical On-Time Delivery (OTD %)",
            "Offered Payment Terms",
            "Freight Responsibility",
            "GST Registration Verified?",
            "Manufacturing Location"
        ],
        "Apex Packaging": ["YES", "YES", "YES", "0.4%", "1.2M pcs", "98.5%", "Net 60", "Supplier Prepaid (DDP)", "YES", "Bhiwandi, MH"],
        "BoxCraft Ltd": ["YES", "NO", "YES", "0.3%", "900K pcs", "96.0%", "Net 30", "Buyer Collect", "YES", "Pune, MH"],
        "CorruSeal Global": ["YES", "YES", "YES", "0.2%", "1.5M pcs", "99.2%", "Net 60", "Supplier Prepaid (DDP)", "YES", "Chennai, TN"],
        "National Paper Mills": ["YES", "YES", "NO", "0.4%", "1.3M pcs", "94.5%", "Net 30", "Buyer Collect", "YES", "Hosur, TN"],
        "PackTech Solutions": ["NO", "YES", "NO", "2.1% (Exceeds 0.5%)", "1.1M pcs", "91.0%", "Net 45", "Supplier Prepaid (DDP)", "YES", "Bengaluru, KA"]
    }
    return pd.DataFrame(data)

# =============================================================================
# PERSISTENT WORKFLOW STATE & DATA SYNCHRONIZATION ENGINE
# =============================================================================
if "stage" not in st.session_state:
    st.session_state.stage = "Create RFQ"

if "rfq_status" not in st.session_state:
    st.session_state.rfq_status = "Draft"

if "rfq_data" not in st.session_state:
    st.session_state.rfq_data = None  # None until user generates RFQ

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

if "user_prompt_input" not in st.session_state:
    st.session_state.user_prompt_input = ""

if "show_publish_review_modal" not in st.session_state:
    st.session_state.show_publish_review_modal = False

def rfq_matches_demo_baseline():
    if st.session_state.rfq_data is None:
        return False
    canonical_df = pd.DataFrame(get_canonical_30_items())
    current_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
    compare_cols = ["Line #", "Description", "Quantity", "UOM", "Specification", "Delivery Location"]
    
    if not all(col in current_df.columns for col in compare_cols):
        return False
        
    return canonical_df[compare_cols].fillna("").astype(str).equals(
        current_df[compare_cols].fillna("").astype(str)
    )

def sync_rfq_to_master_matrix():
    if st.session_state.rfq_data is None:
        return
    rfq_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
    
    # Recalculate extended spend for each line item dynamically
    rfq_df["Est Extended Spend"] = rfq_df.apply(
        lambda r: round(r["Quantity"] * r.get("Target Price (INR)", 0.0), 2), axis=1
    )
    
    base_cols = ["Line #", "Description", "Quantity", "UOM", "Specification", "Delivery Location", "Target Price (INR)", "Est Extended Spend"]
    
    if not all(col in rfq_df.columns for col in base_cols):
        return
        
    rfq_base = rfq_df[base_cols].copy()
    existing = st.session_state.master_matrix.copy()
    
    supplier_cols = [c for c in existing.columns if c not in base_cols]
    existing_supplier_data = existing[["Line #"] + supplier_cols].copy()
    
    merged = rfq_base.merge(existing_supplier_data, on="Line #", how="left")
    st.session_state.master_matrix = merged

def reset_rfq_session():
    st.session_state.rfq_data = None
    st.session_state.rfq_status = "Draft"
    st.session_state.user_prompt_input = ""
    st.session_state.responses_unlocked = False
    st.session_state.compare_unlocked = False
    st.session_state.analyze_unlocked = False
    st.session_state.uploaded_suppliers = set()
    st.session_state.supplier_quote_fingerprints = {}
    st.session_state.processed_file_hashes = set()
    st.session_state.pending_extraction = None
    st.session_state.show_publish_review_modal = False
    st.session_state.master_matrix = get_supplier_prefabricated_dataset()
    st.session_state.questionnaire_matrix = get_questionnaire_master_dataset()
    invalidate_analysis_snapshot()

sync_rfq_to_master_matrix()

# =============================================================================
# DYNAMIC RULE-BASED QUALIFICATION & SPEND ENGINE
# =============================================================================
def calculate_deterministic_spend_engine(df, quest_df, uploaded_suppliers_set, is_demo_mode):
    is_baseline_valid = rfq_matches_demo_baseline()
    current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "") if st.session_state.rfq_data else ""
    
    if is_demo_mode:
        if is_baseline_valid:
            active_suppliers = SUPPLIERS
        else:
            active_suppliers = [s for s in SUPPLIERS if s in uploaded_suppliers_set]
    else:
        active_suppliers = [s for s in SUPPLIERS if s in uploaded_suppliers_set]

    req_iso = st.session_state.rfq_data.get("iso_mandatory", True) if st.session_state.rfq_data else True
    req_esg = st.session_state.rfq_data.get("esg_mandatory", False) if st.session_state.rfq_data else False
    
    defect_str = st.session_state.rfq_data.get("defect_limit", "< 0.5%") if st.session_state.rfq_data else "< 0.5%"
    try:
        max_defect_thresh = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(defect_str))[0])
    except Exception:
        max_defect_thresh = 0.5

    qualification_status = {}
    for sname in SUPPLIERS:
        if sname in quest_df.columns:
            iso_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "ISO 9001 Certification Attached?", sname].values
            esg_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "ESG Audit Certified?", sname].values
            defect_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "3-Year Reported Defect Rate", sname].values
            
            iso_val = str(iso_rows[0]).strip().upper() if len(iso_rows) > 0 else "NO"
            esg_val = str(esg_rows[0]).strip().upper() if len(esg_rows) > 0 else "NO"
            defect_val = defect_rows[0] if len(defect_rows) > 0 else "2.5%"
            
            try:
                defect_num = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(defect_val))[0])
            except Exception:
                defect_num = 1.0
                
            is_iso_valid = (not req_iso) or (iso_val == "YES")
            is_esg_valid = (not req_esg) or (esg_val == "YES")
            is_defect_valid = (defect_num <= max_defect_thresh)
            
            is_qualified = is_iso_valid and is_esg_valid and is_defect_valid
            
            reasons = []
            if req_iso and not is_iso_valid:
                reasons.append(f"ISO 9001 missing")
            if req_esg and not is_esg_valid:
                reasons.append(f"ESG audit missing")
            if not is_defect_valid:
                reasons.append(f"Defect rate ({defect_val}) exceeds limit ({defect_str})")
                
            qualification_status[sname] = {
                "qualified": is_qualified,
                "iso": iso_val,
                "esg": esg_val,
                "defect": defect_val,
                "reason": "Qualified" if is_qualified else "; ".join(reasons)
            }

    supplier_totals = {}
    missing_line_count = 0
    data_quality_count = 0
    stale_quote_suppliers = set()
    exception_line_numbers = set()
    dynamic_issue_descriptions = []
    exception_work_queue = []

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
            lines_usable = 0
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
            lines_usable = len(usable_rows)
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
                    exception_work_queue.append({
                        "Supplier": sname,
                        "Issue Type": "Missing Quote",
                        "Line Item": row["Line #"],
                        "Description": row["Description"],
                        "Impact": "Excluded from scenario comparison"
                    })
                elif st_val == "REVIEW REQUIRED":
                    data_quality_count += 1
                    exception_line_numbers.add(row["Line #"])
                    review_items.append(row["Line #"])
                    exception_work_queue.append({
                        "Supplier": sname,
                        "Issue Type": "Extraction Review Required",
                        "Line Item": row["Line #"],
                        "Description": row["Description"],
                        "Impact": "Price requires human verification"
                    })

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
            "usable_lines": lines_usable,
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
    supplier_allocated_counts = {sname: 0 for sname in active_suppliers if qualification_status[sname]["qualified"]}
    supplier_allocated_spends = {sname: 0.0 for sname in active_suppliers if qualification_status[sname]["qualified"]}
    
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
            supplier_allocated_counts[cheapest_supplier] += 1
            supplier_allocated_spends[cheapest_supplier] += line_total
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
        "supplier_allocated_counts": supplier_allocated_counts,
        "supplier_allocated_spends": supplier_allocated_spends,
        "unassigned_count": unassigned_count,
        "missing_line_count": missing_line_count,
        "data_quality_count": data_quality_count,
        "total_line_exceptions": len(exception_line_numbers),
        "exception_line_numbers": sorted(list(exception_line_numbers)),
        "exception_work_queue": pd.DataFrame(exception_work_queue),
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
elif "Draft" in st.session_state.rfq_status or st.session_state.rfq_data is not None:
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
            <h1 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: {DESIGN_SYSTEM['colors']['text_primary']}; letter-spacing: -0.01em;">
                {st.session_state.rfq_data.get('title', 'Create RFQ') if st.session_state.rfq_data else 'Create RFQ'}
            </h1>
            <div class="rfq-meta-line" style="margin-top: 4px;">
                <span>{f"RFQ-2026-{st.session_state.rfq_data.get('category', 'PKG')[:3].upper()}-001 • {len(st.session_state.rfq_data.get('line_items', []))} SKUs • Deadline {st.session_state.rfq_data.get('response_deadline', '15 Oct 2026')}" if st.session_state.rfq_data else "AI-assisted sourcing setup"}</span>
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
    ("Create RFQ", "01 Create RFQ", True),
    ("Supplier Responses", "02 Supplier Responses", st.session_state.responses_unlocked),
    ("Compare Bids", "03 Compare Bids", st.session_state.compare_unlocked and not st.session_state.pending_extraction),
    ("Analyze & Decide", "04 Analyze & Decide", st.session_state.analyze_unlocked and not st.session_state.pending_extraction)
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
            scroll_to_top()
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# STAGE 1: REQUIREMENTS / CREATE RFQ
# =============================================================================
if st.session_state.stage == "Create RFQ":
    # STATE A: Before "Generate RFQ"
    if st.session_state.rfq_data is None:
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-title'>Turn a sourcing requirement into a structured RFQ</div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-subtitle'>Describe what you're buying, where it is needed, quantities, delivery expectations and any commercial constraints. AI will turn this into an editable RFQ draft.</div>", unsafe_allow_html=True)

            # Fixed feedback #1: Dynamic text area without Ctrl+Enter friction
            prompt_val = st.text_area(
                "Procurement Brief:",
                value=st.session_state.user_prompt_input,
                height=120,
                key="procurement_brief_textarea",
                placeholder="Describe your requirement (e.g., 'Create an RFQ for office furniture for our company across 3 locations. Include 6 line items...')..."
            )
            st.session_state.user_prompt_input = prompt_val
            
            p_col1, p_col2, p_col3 = st.columns([1.5, 1, 1])
            is_brief_empty = not prompt_val.strip()
            
            with p_col1:
                if st.button("Generate RFQ draft →", type="primary", disabled=is_brief_empty, use_container_width=True):
                    with st.spinner("Analyzing brief · Extracting specifications · Structuring SKU line items..."):
                        sys_gen_prompt = """
                        You are an expert enterprise procurement assistant.
                        Analyze the user prompt and generate a structured RFx JSON proposal.
                        JSON Schema required:
                        {
                            "title": "string",
                            "category": "Packaging Materials or Office Furniture & Fixtures or Chemicals & Raw Materials or IT Hardware & Electronics or Logistics & Freight Services",
                            "scope": "string",
                            "delivery_locations": "string",
                            "payment_terms": "string (e.g. Net 60 Days, 30% Advance 70% Installation)",
                            "price_validity": "string (e.g. 60 Days Mandatory, 30 Days)",
                            "freight_terms": "string (e.g. Supplier Prepaid (DDP), Ex-Works)",
                            "iso_mandatory": true,
                            "fsc_mandatory": false,
                            "esg_mandatory": false,
                            "min_capacity": "1.0M pcs",
                            "target_otd": "95.0%",
                            "defect_limit": "< 0.5%",
                            "incoterms_year": "2020",
                            "aql_benchmark": "1.0% AQL",
                            "sample_required": true,
                            "warranty_period": "3 Years Comprehensive",
                            "installation_required": "Vendor Included",
                            "response_deadline": "string",
                            "unclear_specs": [
                                {"requirement": "Installation Charges & Scope", "finding": "Not detailed in brief", "action": "Suggested: Enforce vendor-managed assembly across all locations"}
                            ],
                            "line_items": [
                                {
                                    "Line #": "ITEM-001",
                                    "Description": "Executive Desk",
                                    "Quantity": 15,
                                    "UOM": "pcs",
                                    "Specification": "Teak Finish, Cable Management, 1800x900mm",
                                    "Delivery Location": "Headquarters",
                                    "Target Price (INR)": 28500.00
                                }
                            ]
                        }
                        CRITICAL INSTRUCTION FOR CATEGORY & LINE ITEMS:
                        - Detect category accurately. If brief mentions furniture (desks, chairs, workstations), set category strictly to 'Office Furniture & Fixtures'.
                        - Extract the exact line items requested in brief (e.g. if user asks for 6 furniture line items, generate exactly 6 items corresponding to executive desks, workstations, ergonomic chairs, meeting tables, visitor chairs, and storage cabinets).
                        - Always ensure every line item has a valid non-empty UOM and realistic target unit price in INR.
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
                            
                            category_detected = parsed.get("category", "Office Furniture & Fixtures" if "furniture" in prompt_val.lower() else "Packaging Materials")
                            cat_defaults = CATEGORY_DEFAULTS.get(category_detected, CATEGORY_DEFAULTS["Office Furniture & Fixtures"] if "furniture" in prompt_val.lower() else CATEGORY_DEFAULTS["Packaging Materials"])

                            raw_items = parsed.get("line_items", [])
                            valid_items = []
                            for idx, it in enumerate(raw_items, start=1):
                                q_num = parse_safe_numeric_price(it.get("Quantity")) or 10.0
                                t_price = parse_safe_numeric_price(it.get("Target Price (INR)")) or 15000.0
                                uom_val = str(it.get("UOM", "pcs")).lower().strip()
                                if uom_val not in ["pcs", "kg", "box", "set", "units"]:
                                    uom_val = "pcs"
                                    
                                if it.get("Description"):
                                    it["Line #"] = f"ITEM-{idx:03d}"
                                    it["Quantity"] = int(q_num)
                                    it["UOM"] = uom_val
                                    it["Target Price (INR)"] = t_price
                                    it["Est Extended Spend"] = round(int(q_num) * t_price, 2)
                                    valid_items.append(it)
                                    
                            if len(valid_items) > 0:
                                new_rfq = {
                                    "title": parsed.get("title", f"{category_detected} Sourcing 2026"),
                                    "category": category_detected,
                                    "scope": parsed.get("scope", f"Procurement of {len(valid_items)} line items."),
                                    "delivery_locations": parsed.get("delivery_locations", "Bhiwandi, Hosur & Corporate HQ"),
                                    "payment_terms": parsed.get("payment_terms", cat_defaults["pay_terms"]),
                                    "price_validity": parsed.get("price_validity", cat_defaults["validity"]),
                                    "freight_terms": parsed.get("freight_terms", cat_defaults["freight"]),
                                    "iso_mandatory": parsed.get("iso_mandatory", cat_defaults["iso_default"]),
                                    "fsc_mandatory": parsed.get("fsc_mandatory", cat_defaults.get("fsc_default", False)),
                                    "esg_mandatory": parsed.get("esg_mandatory", cat_defaults["esg_default"]),
                                    "min_capacity": parsed.get("min_capacity", "1.0M pcs"),
                                    "target_otd": parsed.get("target_otd", "95.0%"),
                                    "defect_limit": parsed.get("defect_limit", "< 0.5%"),
                                    "incoterms_year": parsed.get("incoterms_year", "2020"),
                                    "aql_benchmark": parsed.get("aql_benchmark", cat_defaults["aql_default"]),
                                    "sample_required": parsed.get("sample_required", cat_defaults["sample_req"]),
                                    "warranty_period": parsed.get("warranty_period", cat_defaults.get("warranty_default", "3 Years")),
                                    "installation_required": parsed.get("installation_required", cat_defaults.get("installation_default", "Vendor Included")),
                                    "response_deadline": parsed.get("response_deadline", "15 Oct 2026"),
                                    "unclear_specs": parsed.get("unclear_specs", []),
                                    "line_items": valid_items
                                }
                                new_rfq["rfq_fingerprint"] = compute_rfq_fingerprint(new_rfq)
                                st.session_state.rfq_data = new_rfq
                                sync_rfq_to_master_matrix()
                                invalidate_analysis_snapshot()
                                st.session_state.rfq_status = "Draft (AI Generated)"
                                scroll_to_top()
                                st.rerun()
                            else:
                                raise ValueError("AI generated invalid RFQ line items.")
                        except Exception:
                            canon_items = get_canonical_30_items()
                            fallback_rfq = {
                                "title": "Corrugated Packaging Sourcing 2026",
                                "category": "Packaging Materials",
                                "scope": "Procurement of 30 corrugated box SKUs for Western and Southern logistics hubs.",
                                "delivery_locations": "Bhiwandi Warehouse & Hosur Facility",
                                "payment_terms": "Net 60 Days",
                                "price_validity": "60 Days Mandatory",
                                "freight_terms": "Supplier Prepaid (DDP)",
                                "iso_mandatory": True,
                                "fsc_mandatory": False,
                                "esg_mandatory": False,
                                "min_capacity": "1.0M pcs",
                                "target_otd": "95.0%",
                                "defect_limit": "< 0.5%",
                                "incoterms_year": "2020",
                                "aql_benchmark": "1.0% AQL",
                                "sample_required": True,
                                "warranty_period": "3 Years Comprehensive",
                                "installation_required": "Vendor Included",
                                "response_deadline": "15 Oct 2026",
                                "unclear_specs": [
                                    {"requirement": "Peak-season volume buffer", "finding": "Not specified in brief", "action": "Suggested: Enforce 10% volume buffer capacity"}
                                ],
                                "line_items": canon_items
                            }
                            fallback_rfq["rfq_fingerprint"] = compute_rfq_fingerprint(fallback_rfq)
                            st.session_state.rfq_data = fallback_rfq
                            sync_rfq_to_master_matrix()
                            invalidate_analysis_snapshot()
                            st.session_state.rfq_status = "Draft (AI Generated)"
                            scroll_to_top()
                            st.rerun()

            with p_col2:
                if st.button("Try furniture brief", type="secondary", use_container_width=True):
                    st.session_state.user_prompt_input = "Create an RFQ for office furniture for our company across 3 locations. Include 6 line items: executive desks, workstations, ergonomic chairs, meeting tables, visitor chairs, and storage cabinets. Ask vendors to quote unit price, quantity, specifications, material, warranty, delivery timeline, installation charges, taxes, and payment terms."
                    st.rerun()
            with p_col3:
                if st.button("🔄 Reset prompt", type="secondary", use_container_width=True):
                    st.session_state.user_prompt_input = ""
                    st.rerun()

            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.82rem; font-weight:600; color:#475569; margin-bottom:6px;'>WHAT AI WILL GENERATE:</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.82rem; color:#64748B;'>Category-Aware Scope Overview &nbsp;•&nbsp; Custom SKU Line Items & Target Prices &nbsp;•&nbsp; Relevant Commercial Controls &nbsp;•&nbsp; Contextual Quality Benchmarks</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # STATE B: After "Generate RFQ"
    else:
        current_cat = st.session_state.rfq_data.get("category", "Packaging Materials")
        cat_meta = CATEGORY_DEFAULTS.get(current_cat, CATEGORY_DEFAULTS["Packaging Materials"])

        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            
            top_title_col, top_reset_col = st.columns([3, 1])
            with top_title_col:
                st.markdown(f"<div class='section-header-title'>{st.session_state.rfq_data.get('title', 'Procurement RFQ 2026')}</div>", unsafe_allow_html=True)
                st.caption(f"DRAFT · AI GENERATED CATEGORY: **{current_cat.upper()}**")
            with top_reset_col:
                if st.button("🔄 Start New RFQ", type="secondary", use_container_width=True):
                    reset_rfq_session()
                    scroll_to_top()
                    st.rerun()
            
            st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin:16px 0 8px 0;'>RFQ Summary Cards</div>", unsafe_allow_html=True)
            
            # Equal Height KPI Grid
            ov1, ov2, ov3, ov4, ov5 = st.columns(5)
            with ov1:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Category & Scope</div><div class='kpi-value'>{len(st.session_state.rfq_data.get('line_items', []))} SKUs</div><div class='kpi-subtext'>{current_cat}</div></div>", unsafe_allow_html=True)
            with ov2:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Locations</div><div class='kpi-value' style='font-size:1.0rem;'>{st.session_state.rfq_data.get('delivery_locations', '3 Logistics Hubs')}</div><div class='kpi-subtext'>Delivery hubs</div></div>", unsafe_allow_html=True)
            with ov3:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Deadline</div><div class='kpi-value' style='font-size:1.1rem;'>{st.session_state.rfq_data.get('response_deadline', '15 Oct 2026')}</div><div class='kpi-subtext'>Response window</div></div>", unsafe_allow_html=True)
            with ov4:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Payment & Incoterm</div><div class='kpi-value' style='font-size:0.95rem;'>{st.session_state.rfq_data.get('payment_terms', 'Net 60 Days')}</div><div class='kpi-subtext'>{st.session_state.rfq_data.get('incoterms_year', '2020')} Terms</div></div>", unsafe_allow_html=True)
            with ov5:
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Freight & Logistics</div><div class='kpi-value' style='font-size:0.95rem;'>{st.session_state.rfq_data.get('freight_terms', 'Supplier Prepaid (DDP)')}</div><div class='kpi-subtext'>Delivery terms</div></div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        # Fixed feedback #4: Context-aware Category Specific Commercial & Qualification Controls
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown(f"<div class='section-header-title'>Commercial & Qualification Controls ({current_cat})</div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-subtitle'>Showing only parameters relevant to this category requirement. Controls update dynamically.</div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Commercial & Delivery Parameters</div>", unsafe_allow_html=True)
                
                pay_opts = ["Net 60 Days", "Net 30 Days", "30% Advance, 70% Post-Installation", "Net 45 Days", "Advance Payment"]
                curr_pay = st.session_state.rfq_data.get("payment_terms", cat_meta["pay_terms"])
                pay_idx = pay_opts.index(curr_pay) if curr_pay in pay_opts else 0
                selected_pay = st.selectbox("Payment terms:", options=pay_opts, index=pay_idx)
                
                val_opts = ["60 Days Mandatory", "30 Days", "90 Days"]
                curr_val = st.session_state.rfq_data.get("price_validity", cat_meta["validity"])
                val_idx = val_opts.index(curr_val) if curr_val in val_opts else 0
                selected_val = st.selectbox("Price validity:", options=val_opts, index=val_idx)
                
                fr_opts = ["Supplier Prepaid (DDP)", "Ex-Works", "FOB Destination"]
                curr_fr = st.session_state.rfq_data.get("freight_terms", cat_meta["freight"])
                fr_idx = fr_opts.index(curr_fr) if curr_fr in fr_opts else 0
                selected_fr = st.selectbox("Freight terms:", options=fr_opts, index=fr_idx)

                sub_c1, sub_c2 = st.columns(2)
                with sub_c1:
                    incoterm_val = st.selectbox("Incoterms standard:", options=["DDP (2020)", "FOB (2020)", "EXW (2020)"], index=0)
                with sub_c2:
                    sample_m = st.toggle("Pre-award sample / catalog approval mandatory", value=st.session_state.rfq_data.get("sample_required", cat_meta["sample_req"]))

                if cat_meta.get("installation_visible", False):
                    inst_opts = ["Vendor Included (Turnkey)", "Buyer Direct Assembly", "Optional Add-On"]
                    curr_inst = st.session_state.rfq_data.get("installation_required", cat_meta.get("installation_default", "Vendor Included (Turnkey)"))
                    inst_idx = inst_opts.index(curr_inst) if curr_inst in inst_opts else 0
                    selected_inst = st.selectbox("Installation & Assembly Scope:", options=inst_opts, index=inst_idx)
                    st.session_state.rfq_data["installation_required"] = selected_inst

                st.session_state.rfq_data["payment_terms"] = selected_pay
                st.session_state.rfq_data["price_validity"] = selected_val
                st.session_state.rfq_data["freight_terms"] = selected_fr
                st.session_state.rfq_data["incoterms_year"] = incoterm_val
                st.session_state.rfq_data["sample_required"] = sample_m

            with c2:
                st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Supplier Qualification & Quality Benchmarks</div>", unsafe_allow_html=True)
                
                iso_m = st.toggle("ISO 9001 certification mandatory", value=st.session_state.rfq_data.get("iso_mandatory", cat_meta["iso_default"]))
                esg_m = st.toggle("ESG / E-Waste / Environmental audit mandatory", value=st.session_state.rfq_data.get("esg_mandatory", cat_meta["esg_default"]))
                
                # Render FSC toggle only if relevant (e.g. Packaging)
                if cat_meta.get("fsc_visible", False):
                    fsc_m = st.toggle("FSC sustainability certification mandatory", value=st.session_state.rfq_data.get("fsc_mandatory", cat_meta["fsc_default"]))
                    st.session_state.rfq_data["fsc_mandatory"] = fsc_m
                else:
                    st.session_state.rfq_data["fsc_mandatory"] = False

                q_sub1, q_sub2 = st.columns(2)
                with q_sub1:
                    def_opts = ["< 0.5%", "< 1.0%", "< 0.2%"]
                    curr_def = st.session_state.rfq_data.get("defect_limit", "< 0.5%")
                    def_idx = def_opts.index(curr_def) if curr_def in def_opts else 0
                    selected_def = st.selectbox("Max defect rate limit:", options=def_opts, index=def_idx)
                    st.session_state.rfq_data["defect_limit"] = selected_def
                
                with q_sub2:
                    if cat_meta.get("warranty_visible", False):
                        warr_opts = ["3 Years Comprehensive", "1 Year On-Site", "5 Years Extended", "1 Year Standard"]
                        curr_warr = st.session_state.rfq_data.get("warranty_period", cat_meta.get("warranty_default", "3 Years Comprehensive"))
                        warr_idx = warr_opts.index(curr_warr) if curr_warr in warr_opts else 0
                        selected_warr = st.selectbox("Mandatory Warranty Period:", options=warr_opts, index=warr_idx)
                        st.session_state.rfq_data["warranty_period"] = selected_warr
                    elif cat_meta.get("aql_visible", True):
                        aql_opts = ["1.0% AQL", "0.5% AQL", "0.25% AQL"]
                        selected_aql = st.selectbox("Quality AQL benchmark:", options=aql_opts, index=0)
                        st.session_state.rfq_data["aql_benchmark"] = selected_aql

                st.session_state.rfq_data["iso_mandatory"] = iso_m
                st.session_state.rfq_data["esg_mandatory"] = esg_m

            st.markdown("</div>", unsafe_allow_html=True)

        # Actionable "Review Before Publishing" Drawer
        active_unclear = []
        for spec in st.session_state.rfq_data.get("unclear_specs", []):
            req_name = spec.get("requirement", "").lower()
            if "validity" in req_name and st.session_state.rfq_data.get("price_validity"):
                continue
            if "payment" in req_name and st.session_state.rfq_data.get("payment_terms"):
                continue
            if "freight" in req_name and st.session_state.rfq_data.get("freight_terms"):
                continue
            active_unclear.append(spec)

        if active_unclear:
            with st.container():
                st.markdown("<div class='aerchain-section' style='border: 1px solid #FEF08A; background-color: #FFFBEB; padding: 16px; border-radius: 6px;'>", unsafe_allow_html=True)
                st.markdown("<div class='section-header-title' style='color:#B45309;'>Unresolved Brief Parameter Warnings</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='section-header-subtitle' style='color:#B45309;'>{len(active_unclear)} item(s) flagged by AI need confirmation before final publishing.</div>", unsafe_allow_html=True)
                
                for idx, spec in enumerate(active_unclear):
                    c_spec1, c_spec2, c_spec3 = st.columns([2, 3, 1])
                    with c_spec1:
                        st.markdown(f"**{spec.get('requirement', 'Requirement')}**")
                    with c_spec2:
                        st.markdown(f"{spec.get('finding', 'Not specified')} → *{spec.get('action', 'Action required')}*")
                    with c_spec3:
                        if st.button(f"Confirm & Apply", key=f"confirm_spec_{idx}", type="secondary", use_container_width=True):
                            if "installation" in spec.get("requirement", "").lower():
                                st.session_state.rfq_data["scope"] += " (Enforcing vendor turnkey installation)"
                            elif "buffer" in spec.get("requirement", "").lower():
                                st.session_state.rfq_data["scope"] += " (Enforcing 10% peak volume buffer)"
                            st.session_state.rfq_data["unclear_specs"] = [s for s in st.session_state.rfq_data["unclear_specs"] if s.get("requirement") != spec.get("requirement")]
                            st.toast(f"✓ Applied parameter: {spec.get('requirement')}", icon="✅")
                            st.rerun()
                            
                st.markdown("</div>", unsafe_allow_html=True)

        # Line Items Editor (Meaningful Columns: Target Price & Est Extended Spend)
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown(f"<div class='section-header-title'>Line Items ({len(st.session_state.rfq_data['line_items'])} SKUs)</div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-subtitle'>Review quantities, UOMs, target unit prices, and estimated extended budget spend before publishing.</div>", unsafe_allow_html=True)
            
            items_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
            
            edited_items = st.data_editor(
                items_df,
                use_container_width=True,
                height=320,
                hide_index=True,
                column_config={
                    "Line #": st.column_config.TextColumn("Line #", disabled=True, width="small"),
                    "Description": st.column_config.TextColumn("Description", width="medium"),
                    "Quantity": st.column_config.NumberColumn("Quantity", format="%d", min_value=1, width="small"),
                    "UOM": st.column_config.SelectboxColumn("UOM", options=["pcs", "kg", "box", "set", "units"], width="small"),
                    "Specification": st.column_config.TextColumn("Specification", width="medium"),
                    "Delivery Location": st.column_config.TextColumn("Delivery Location", width="small"),
                    "Target Price (INR)": st.column_config.NumberColumn("Target Price (INR)", format="₹%.2f", width="small"),
                    "Est Extended Spend": st.column_config.NumberColumn("Est Extended Spend", format="₹%.2f", disabled=True, width="medium")
                }
            )
            
            has_invalid_qty = (edited_items["Quantity"] <= 0).any()
            if has_invalid_qty:
                st.error("⚠ Invalid Quantity detected: All line item quantities must be greater than 0.")
                
            edited_records = edited_items.to_dict(orient="records")
            old_fp = st.session_state.rfq_data.get("rfq_fingerprint")
            st.session_state.rfq_data["line_items"] = edited_records
            new_fp = compute_rfq_fingerprint(st.session_state.rfq_data)
            st.session_state.rfq_data["rfq_fingerprint"] = new_fp
            
            if old_fp != new_fp:
                sync_rfq_to_master_matrix()
                invalidate_analysis_snapshot()

            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            f1, f2, f3 = st.columns([2, 1, 1])
            with f2:
                if st.button("Save draft", type="secondary", use_container_width=True):
                    st.session_state.rfq_status = "Draft (Saved)"
                    st.toast("✓ RFQ draft saved successfully! All parameters preserved.", icon="💾")
            with f3:
                # Fixed feedback #3: Review before publishing workflow step
                if st.button("Review & Publish RFQ →", type="primary", disabled=has_invalid_qty, use_container_width=True):
                    st.session_state.show_publish_review_modal = True
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        # Fixed feedback #3: Executive Pre-Publish Review Summary Modal Container
        if st.session_state.show_publish_review_modal:
            with st.container():
                st.markdown("<div class='aerchain-section' style='background-color:#F0F9FF; border:1px solid #BAE6FD; padding:20px; border-radius:8px;'>", unsafe_allow_html=True)
                st.markdown("<div class='section-header-title' style='color:#0369A1;'>📋 Pre-Publishing RFQ Executive Summary Review</div>", unsafe_allow_html=True)
                st.markdown("<div class='section-header-subtitle' style='color:#0369A1;'>Please verify all final sourcing controls before publishing this RFQ to supplier portals.</div>", unsafe_allow_html=True)
                
                rev_col_a, rev_col_b = st.columns(2)
                with rev_col_a:
                    st.markdown(f"**RFQ Title:** {st.session_state.rfq_data.get('title')}")
                    st.markdown(f"**Category:** {st.session_state.rfq_data.get('category')}")
                    st.markdown(f"**Total SKUs / Line Items:** {len(st.session_state.rfq_data.get('line_items', []))}")
                    st.markdown(f"**Delivery Locations:** {st.session_state.rfq_data.get('delivery_locations')}")
                    st.markdown(f"**Payment Terms:** {st.session_state.rfq_data.get('payment_terms')}")
                with rev_col_b:
                    st.markdown(f"**Freight Terms:** {st.session_state.rfq_data.get('freight_terms')}")
                    st.markdown(f"**Price Validity Required:** {st.session_state.rfq_data.get('price_validity')}")
                    st.markdown(f"**ISO 9001 Mandatory:** {'Yes' if st.session_state.rfq_data.get('iso_mandatory') else 'No'}")
                    if st.session_state.rfq_data.get("warranty_period"):
                        st.markdown(f"**Warranty Requirement:** {st.session_state.rfq_data.get('warranty_period')}")
                    if st.session_state.rfq_data.get("installation_required"):
                        st.markdown(f"**Installation Scope:** {st.session_state.rfq_data.get('installation_required')}")

                tot_budget = sum([it.get('Est Extended Spend', 0.0) for it in st.session_state.rfq_data.get('line_items', [])])
                st.info(f"💰 **Estimated Target RFQ Budget:** ₹{tot_budget:,.2f} across {len(st.session_state.rfq_data.get('line_items', []))} items.")

                m_btn1, m_btn2 = st.columns([1, 1])
                with m_btn1:
                    if st.button("← Back to editing", type="secondary", use_container_width=True):
                        st.session_state.show_publish_review_modal = False
                        st.rerun()
                with m_btn2:
                    if st.button("🚀 Confirm & Publish RFQ Now", type="primary", use_container_width=True):
                        st.session_state.rfq_status = "Published"
                        st.session_state.responses_unlocked = True
                        st.session_state.show_publish_review_modal = False
                        st.toast("🚀 RFQ Successfully Published! Unlocking Supplier Responses...", icon="✅")
                        st.session_state.stage = "Supplier Responses"
                        scroll_to_top()
                        st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# STAGE 2: SUPPLIER RESPONSES & EXTRACTION
# =============================================================================
elif st.session_state.stage == "Supplier Responses":
    with st.container():
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
            info = calc["supplier_totals"].get(sname, {"lines_quoted": 0, "usable_lines": 0, "total_lines": len(st.session_state.master_matrix), "is_complete": False, "is_stale": False})
            q_info = calc["qualification_status"].get(sname, {"qualified": False})
            
            coverage = f"{info['lines_quoted']} quoted · {info['usable_lines']} usable / {info['total_lines']} lines" if is_active else "Excluded (Reference Only)"
            qual_str = "Qualified" if q_info["qualified"] else "Disqualified"
            
            if info.get("is_stale"):
                data_qual = "STALE — REVALIDATION REQUIRED"
            else:
                data_qual = "Complete" if info["is_complete"] else ("Review Required" if info.get("has_review") else "Incomplete / Missing")
                
            receipt_str = "Quote received" if sname in st.session_state.uploaded_suppliers else ("Baseline loaded" if st.session_state.demo_mode else "Not submitted")
            
            inbox_rows.append({
                "Supplier": sname,
                "Receipt": receipt_str,
                "Coverage Details": coverage,
                "Qualification": qual_str,
                "Data Quality": data_qual,
                "Offered Terms": st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Offered Payment Terms", sname].values[0]
            })
            
        st.dataframe(pd.DataFrame(inbox_rows), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Document Extraction Workspace Section
    with st.container():
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
                                     "verbatim_snippet": "string (exact raw excerpt surrounding price quote)",
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

            valid_rfq_map = {it["Line #"]: it for it in (st.session_state.rfq_data["line_items"] if st.session_state.rfq_data else get_canonical_30_items())}
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
                verb_snip = item.get("verbatim_snippet", orig_verbatim or "Raw quote excerpt from document")
                
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
                    "Normalized INR": norm_price if norm_price is not None else "—",
                    "How it was normalized": basis_desc,
                    "Source": src_ref,
                    "Verbatim Snippet": verb_snip,
                    "Extraction confidence": conf_str,
                    "Validation Status": status_str,
                    "Source Type": "Supplier Submitted"
                })
            
            extracted_total = len(review_table)
            
            st.dataframe(
                pd.DataFrame(review_table)[["Line #", "Original Quote", "Normalized INR", "How it was normalized", "Source", "Extraction confidence", "Validation Status"]],
                use_container_width=True,
                height=220,
                hide_index=True
            )
            
            with st.popover("Inspect Raw Document Snippets & Provenance Evidence"):
                st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A;'>Document Provenance Inspector</div>", unsafe_allow_html=True)
                st.caption(f"Verbatim text excerpts parsed from `{st.session_state.pending_extraction['file_name']}` for {sname}")
                for row_entry in review_table:
                    if "REJECTED" not in row_entry["Validation Status"]:
                        with st.expander(f"Line {row_entry['Line #']}: {row_entry['Original Quote']} ({row_entry['Validation Status']})"):
                            st.markdown(f"**Source Reference:** `{row_entry['Source']}`")
                            st.markdown(f"**Extraction Confidence:** `{row_entry['Extraction confidence']}`")
                            st.markdown(f"**Normalization Basis:** {row_entry['How it was normalized']}")
                            st.markdown("**Verbatim Document Snippet:**")
                            st.code(row_entry['Verbatim Snippet'], language="text")

            st.caption(f"Extraction Summary: **{extracted_total} extracted** · **{validated_count} validated** · **{needs_review_count} require review** · **{rejected_count} rejected**")
            
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
                    snippet_col = meta["snippet_col"]
                    
                    st.session_state.master_matrix[norm_col] = None
                    st.session_state.master_matrix[orig_col] = "NOT QUOTED"
                    st.session_state.master_matrix[status_col] = "MISSING"
                    st.session_state.master_matrix[conf_col] = "0%"
                    st.session_state.master_matrix[source_col] = "N/A"
                    st.session_state.master_matrix[snippet_col] = "Line unquoted in submission."

                    for row_entry in review_table:
                        if "REJECTED" not in row_entry["Validation Status"]:
                            lnum = row_entry["Line #"]
                            norm_val = row_entry["Normalized INR"]
                            orig_rep = row_entry["Original Quote"]
                            status_val = row_entry["Validation Status"]
                            conf_val = row_entry["Extraction confidence"]
                            src_val = row_entry["Source"]
                            snip_val = row_entry["Verbatim Snippet"]
                            
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, norm_col] = norm_val
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, orig_col] = orig_rep
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, status_col] = status_val
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, conf_col] = conf_val
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, source_col] = src_val
                            st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, snippet_col] = snip_val
                            
                    st.session_state.uploaded_suppliers.add(sname)
                    st.session_state.supplier_quote_fingerprints[sname] = st.session_state.rfq_data.get("rfq_fingerprint", "") if st.session_state.rfq_data else ""
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
            scroll_to_top()
            st.rerun()
    with b2:
        if st.button("Continue to Compare Quotes →", type="primary", disabled=bool(st.session_state.pending_extraction)):
            st.session_state.compare_unlocked = True
            st.session_state.stage = "Compare Bids"
            scroll_to_top()
            st.rerun()

# =============================================================================
# STAGE 3: COMPARE QUOTES & COMPLIANCE
# =============================================================================
elif st.session_state.stage == "Compare Bids":
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Supplier Pricing & Qualification Matrix</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Compare normalized unit prices, coverage and qualification status. Values marked Review Required or Stale are excluded from sourcing calculations.</div>", unsafe_allow_html=True)

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
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Complete Quotes</div><div class='kpi-value'>{sum(1 for k in calc['active_suppliers'] if calc['supplier_totals'][k]['is_complete'])}</div><div class='kpi-subtext'>100% coverage</div></div>", unsafe_allow_html=True)
        with s3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Vendors</div><div class='kpi-value'>{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}</div><div class='kpi-subtext'>Passed compliance</div></div>", unsafe_allow_html=True)
        with s4:
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
                "Source": "Supplier Submitted" if sname in st.session_state.uploaded_suppliers else "Demo Baseline",
                "Coverage Details": f"{info['lines_quoted']} quoted · {info['usable_lines']} usable / {info['total_lines']} lines",
                "Qualification": "Qualified" if q_info['qualified'] else "Disqualified",
                "Data Quality": dq_str,
                "Quoted spend": spend_str
            })
            
        if summary_rows:
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No supplier responses uploaded yet. Upload a supplier quotation in Stage 2 or toggle 'Include demo baseline data' above.")

        if calc["dynamic_issue_descriptions"]:
            with st.expander(f"Issues requiring attention · {calc['total_line_exceptions']} lines affected"):
                for issue_desc in calc["dynamic_issue_descriptions"]:
                    st.markdown(f"* {issue_desc}")

        st.markdown("</div>", unsafe_allow_html=True)

    # Matrix Section
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        tab_comp1, tab_comp2 = st.tabs(["Price comparison matrix", "Qualification & Analyst Checks"])
        
        with tab_comp1:
            m_col1, m_col2 = st.columns([2, 1])
            with m_col1:
                st.session_state.exception_filter = st.selectbox(
                    "Filter matrix view:",
                    ["All line items", "Quoted lines with exceptions"]
                )
            with m_col2:
                st.markdown("<div style='text-align: right; font-size: 0.8rem; color: #64748B; padding-top: 28px;'>Normalized unit price (INR / unit)</div>", unsafe_allow_html=True)
            
            matrix_cols = ["Line #", "Description", "Quantity", "UOM", "Target Price (INR)"]
            for sname in calc["active_suppliers"]:
                matrix_cols.append(SUPPLIER_MAP[sname]["norm_col"])
                
            matrix_display = st.session_state.master_matrix[matrix_cols].copy()
            
            col_rename_map = {"Quantity": "Qty", "Target Price (INR)": "Target (₹)"}
            for sname in calc["active_suppliers"]:
                col_rename_map[SUPPLIER_MAP[sname]["norm_col"]] = SUPPLIER_MAP[sname]["prefix"].upper()
            matrix_display = matrix_display.rename(columns=col_rename_map)

            if calc["active_suppliers"]:
                meta_cols = st.columns([1, 2.5, 0.8, 0.8, 0.8] + [1.5] * len(calc["active_suppliers"]))
                for idx, sname in enumerate(calc["active_suppliers"]):
                    q_lbl = "QUALIFIED" if calc["qualification_status"].get(sname, {}).get("qualified", False) else "DISQUALIFIED"
                    prov_lbl = "Submitted" if sname in st.session_state.uploaded_suppliers else "Demo"
                    with meta_cols[5 + idx]:
                        st.caption(f"**{q_lbl}**\n\n{prov_lbl}")
            
            if st.session_state.exception_filter == "Quoted lines with exceptions":
                matrix_display = matrix_display[matrix_display["Line #"].isin(calc["exception_line_numbers"])]

            for sname in calc["active_suppliers"]:
                col_key = SUPPLIER_MAP[sname]["prefix"].upper()
                if col_key in matrix_display.columns:
                    matrix_display[col_key] = matrix_display[col_key].astype(str).replace(["nan", "None", "<NA>"], "—")

            def style_matrix_cells(row):
                styles = [''] * len(row)
                
                qual_col_indices = []
                for col_idx in range(5, len(row)):
                    sname = calc["active_suppliers"][col_idx - 5]
                    info = calc["supplier_totals"].get(sname, {})
                    if info.get("qualified", False) and not info.get("is_stale", False):
                        qual_col_indices.append(col_idx)

                valid_prices = {}
                for col_idx in range(5, len(row)):
                    val = row.iloc[col_idx]
                    sname = calc["active_suppliers"][col_idx - 5]
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
            st.dataframe(styled_matrix, use_container_width=True, height=380, hide_index=True)
            
            with st.popover("Inspect Document Evidence & Provenance Side-by-Side"):
                st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A;'>Line-Item Document Evidence Inspector</div>", unsafe_allow_html=True)
                st.caption("Verbatim source excerpts and extraction confidence for all active supplier quotes")
                
                line_select = st.selectbox("Select Line Item to Inspect:", st.session_state.master_matrix["Line #"].tolist())
                line_row = st.session_state.master_matrix[st.session_state.master_matrix["Line #"] == line_select].iloc[0]
                
                st.markdown(f"**SKU:** `{line_row['Line #']}` — {line_row['Description']} ({line_row['Quantity']:,} {line_row['UOM']})")
                st.markdown("---")
                
                num_active = len(calc["active_suppliers"])
                if num_active > 0:
                    p_cols = st.columns(num_active)
                    for idx, sname in enumerate(calc["active_suppliers"]):
                        meta = SUPPLIER_MAP[sname]
                        with p_cols[idx]:
                            st.markdown(f"**{sname}**")
                            st.markdown(f"Quote: `{line_row.get(meta['orig_col'], '—')}`")
                            st.markdown(f"Norm. INR: `₹{line_row.get(meta['norm_col'], '—')}`")
                            st.markdown(f"Status: `{line_row.get(meta['status_col'], '—')}`")
                            st.markdown(f"Confidence: `{line_row.get(meta['conf_col'], '—')}`")
                            st.markdown(f"Ref: `{line_row.get(meta['source_col'], 'N/A')}`")
                            st.caption("Verbatim Snippet:")
                            st.code(line_row.get(meta['snippet_col'], "No snippet available."), language="text")
                else:
                    st.info("No active suppliers to inspect. Upload supplier documents or enable Demo Mode.")

            st.markdown("""
            <div style="font-size: 0.78rem; color: #64748B; margin-top: 6px;">
                <strong>Legend:</strong> &nbsp;
                <span style="background-color: #F0FDF4; color: #166534; padding: 2px 6px; border-radius: 4px; border: 1px solid #BBF7D0;">Lowest usable qualified price — price comparison only, not an award recommendation</span> &nbsp;
                <span style="background-color: #FFFBEB; color: #B45309; padding: 2px 6px; border-radius: 4px; border: 1px solid #FEF08A;">Review required (excluded from sourcing)</span> &nbsp;
                <span>— Missing / unquoted</span>
            </div>
            """, unsafe_allow_html=True)

        with tab_comp2:
            st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:4px;'>Qualification & Compliance Matrix</div>", unsafe_allow_html=True)
            st.caption("Evaluates active ISO, ESG, FSC, OTD % and Defect Rate constraints dynamically.")
            
            qual_summary = []
            for sname in calc["active_suppliers"]:
                q_info = calc["qualification_status"][sname]
                otd_val = st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Historical On-Time Delivery (OTD %)", sname].values[0] if sname in st.session_state.questionnaire_matrix.columns else "N/A"
                
                qual_summary.append({
                    "Supplier": sname,
                    "ISO 9001": q_info["iso"],
                    "ESG Audit": q_info["esg"],
                    "3-Year Defect Rate": q_info["defect"],
                    "Historical OTD %": otd_val,
                    "Qualification": "Qualified" if q_info["qualified"] else "Disqualified",
                    "Reason / Evaluation": q_info["reason"]
                })
            if qual_summary:
                st.dataframe(pd.DataFrame(qual_summary), use_container_width=True, hide_index=True)
            else:
                st.info("No active suppliers available.")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    cb1, cb2 = st.columns([1, 1])
    with cb1:
        if st.button("← Back to Responses", type="secondary"):
            st.session_state.stage = "Supplier Responses"
            scroll_to_top()
            st.rerun()
    with cb2:
        if st.button("Continue to Scenario Analysis →", type="primary"):
            st.session_state.analyze_unlocked = True
            st.session_state.stage = "Analyze & Decide"
            scroll_to_top()
            st.rerun()

# =============================================================================
# STAGE 4: PROCUREMENT DECISION WORKSPACE
# =============================================================================
elif st.session_state.stage == "Analyze & Decide":
    # 1. Compact Header
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Procurement Decision Workspace</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle' style='margin-bottom:0;'>Analyze supplier eligibility, audit exceptions, evaluate price-only split economics, and verify PO pre-requisites.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    current_dataset_fp = compute_dataset_fingerprint()

    # 2. Interactive Sourcing Query Bar
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:6px;'>Ask about your sourcing data</div>", unsafe_allow_html=True)
        
        q_btn_1, q_btn_2, q_btn_3, q_btn_4 = st.columns(4)
        prompt_choice = None
        
        if q_btn_1.button("Who is eligible?", type="secondary", use_container_width=True):
            prompt_choice = "Which suppliers are eligible for a price-only comparison?"
        if q_btn_2.button("What if we split?", type="secondary", use_container_width=True):
            prompt_choice = "What happens if we split the award across qualified suppliers based on lowest usable price?"
        if q_btn_3.button("Which lines need review?", type="secondary", use_container_width=True):
            prompt_choice = "Which lines still need human review or revalidation?"
        if q_btn_4.button("Why no landed cost?", type="secondary", use_container_width=True):
            prompt_choice = "Why can't you give me landed cost yet?"

        user_query = st.text_input(
            "Enter sourcing question:",
            value=prompt_choice if prompt_choice else (st.session_state.last_analysis_query if st.session_state.last_analysis_query else "Which suppliers are eligible for a price-only comparison?"),
            placeholder="e.g. Which suppliers are eligible for a price-only comparison?",
            label_visibility="collapsed"
        )

        if st.button("Ask →", type="primary"):
            if user_query:
                with st.spinner("Analyzing sourcing data..."):
                    matrix_json = st.session_state.master_matrix.to_json(orient="records")
                    q_json = st.session_state.questionnaire_matrix.to_json(orient="records")
                    
                    disqualified_list = [f"{s} ({info['reason']})" for s, info in calc['qualification_status'].items() if (s in calc['active_suppliers'] and not info['qualified'])]
                    disqual_str = "; ".join(disqualified_list) if disqualified_list else "None"
                    delta_direction = "lower" if calc['price_diff'] >= 0 else "higher"

                    system_instruction = f"""
                    You are an enterprise procurement analysis assistant.
                    Analyze RFx data across suppliers: {', '.join(calc['active_suppliers'])}.
                    
                    STRICT GROUNDING & INTENT ROUTING RULES:
                    1. First identify user intent from query: 'eligibility', 'split_scenario', 'exceptions', or 'landed_cost'.
                    2. Provide clean JSON response matching intent:
                       {{
                           "intent": "eligibility | split_scenario | exceptions | landed_cost",
                           "headline_answer": "One concise executive sentence answering the EXACT question asked.",
                           "key_drivers": ["bullet point 1", "bullet point 2"],
                           "trade_offs": ["bullet point 1", "bullet point 2"],
                           "data_gaps": ["bullet point 1"]
                       }}
                    3. Do NOT invent numbers. Spend facts:
                       - Lowest Qualified Single Quote: {calc['best_single_name']} (₹{calc['best_single_spend']:,.0f})
                       - Split Scenario Spend: ₹{calc['split_spend']:,.0f} (Unassigned lines: {calc['unassigned_count']})
                       - Delta: ₹{abs(calc['price_diff']):,.0f} {delta_direction} ({calc['price_diff_pct']}%)
                       - Disqualified: {disqual_str}
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
                            "demo_mode": st.session_state.demo_mode
                        }
                    except Exception:
                        st.error("Scenario evaluation failed. Please refine query.")

        st.markdown("</div>", unsafe_allow_html=True)

    # 3. Intent-Specific Answer Header & Findings
    if st.session_state.last_analysis_result:
        parsed_ans = st.session_state.last_analysis_result
        active_intent = parsed_ans.get("intent", "eligibility")
        
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-title'>Primary Sourcing Findings</div>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='margin: 4px 0 16px 0; font-size: 1.15rem; font-weight: 600; color: #0F172A;'>{parsed_ans.get('headline_answer', '')}</h3>", unsafe_allow_html=True)
            
            if active_intent == "eligibility" or "eligib" in st.session_state.last_analysis_query.lower():
                st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Supplier Eligibility & Coverage Breakdown</div>", unsafe_allow_html=True)
                
                elig_rows = []
                for sname in calc["active_suppliers"]:
                    q_info = calc["qualification_status"][sname]
                    s_info = calc["supplier_totals"][sname]
                    
                    q_badge = "Qualified" if q_info["qualified"] else "Not qualified"
                    cov_str = f"{s_info['lines_quoted']} / {s_info['total_lines']}"
                    
                    if not q_info["qualified"]:
                        status_str = f"Excluded ({q_info['reason']})"
                    elif s_info["has_review"]:
                        status_str = "Review required"
                    else:
                        status_str = "Usable"

                    elig_rows.append({
                        "Supplier": sname,
                        "Qualification": q_badge,
                        "Quote coverage": cov_str,
                        "Data status": status_str
                    })
                
                st.dataframe(pd.DataFrame(elig_rows), use_container_width=True, hide_index=True)
                
                disqual_suppliers = [s for s in calc["active_suppliers"] if not calc["qualification_status"][s]["qualified"]]
                if disqual_suppliers:
                    st.markdown("<div style='margin-top:12px; font-size:0.83rem; color:#991B1B;'><strong>Why Excluded:</strong></div>", unsafe_allow_html=True)
                    for ds in disqual_suppliers:
                        st.markdown(f"<div style='font-size:0.82rem; color:#475569;'>• <strong>{ds}:</strong> {calc['qualification_status'][ds]['reason']}</div>", unsafe_allow_html=True)

            elif active_intent == "landed_cost" or "landed" in st.session_state.last_analysis_query.lower():
                st.warning("Landed cost cannot be calculated due to missing numerical GST rates and freight cost inputs.")
                lc_rows = []
                for sname in calc["active_suppliers"]:
                    freight_term = st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Freight Responsibility", sname].values[0]
                    lc_rows.append({
                        "Supplier": sname,
                        "Base Price": "Available",
                        "Freight Terms": freight_term,
                        "Freight Cost Amount": "Missing in submission",
                        "GST Rate (%)": "Missing in submission"
                    })
                st.dataframe(pd.DataFrame(lc_rows), use_container_width=True, hide_index=True)

            st.markdown("</div>", unsafe_allow_html=True)

    # 4. Actionable Exception Work Queue
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-header-title'>{calc['total_line_exceptions']} Lines Need Attention</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Operational queue of missing quotes, low-confidence OCR extractions, and compliance exceptions.</div>", unsafe_allow_html=True)
        
        if not calc["exception_work_queue"].empty:
            st.dataframe(calc["exception_work_queue"], use_container_width=True, height=200, hide_index=True)
            
            ex_c1, ex_c2 = st.columns([1.5, 1])
            with ex_c1:
                if st.button("Review exceptions in comparison matrix →", type="secondary"):
                    st.session_state.exception_filter = "Quoted lines with exceptions"
                    st.session_state.stage = "Compare Bids"
                    scroll_to_top()
                    st.rerun()
        else:
            st.success("✓ Zero line-item exceptions detected across active suppliers.")
            
        st.markdown("</div>", unsafe_allow_html=True)

    # 5. Price-Only Sourcing Scenario & Visual Allocation
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Price-Only Sourcing Scenario</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Price-only baseline scenario assuming lowest unit price allocation across qualified suppliers. Freight, GST, capacity, and lead times are excluded.</div>", unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns(4)
        total_items_count = len(st.session_state.rfq_data["line_items"]) if st.session_state.rfq_data else 30
        assigned_lines = total_items_count - calc["unassigned_count"]
        
        with sc1:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Split Spend</div><div class='kpi-value'>₹{calc['split_spend']/100000:.2f}L</div><div class='kpi-subtext'>Illustrative baseline</div></div>", unsafe_allow_html=True)
        with sc2:
            single_val_str = f"₹{calc['best_single_spend']/100000:.2f}L" if calc['has_complete_option'] else "N/A"
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Lowest Single Quote</div><div class='kpi-value'>{single_val_str}</div><div class='kpi-subtext'>{calc['best_single_name']}</div></div>", unsafe_allow_html=True)
        with sc3:
            diff_val_str = f"₹{abs(calc['price_diff'])/1000:.1f}K ({calc['price_diff_pct']}%)" if calc['has_complete_option'] else "N/A"
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Price Difference</div><div class='kpi-value'>{diff_val_str}</div><div class='kpi-subtext'>Vs lowest complete single</div></div>", unsafe_allow_html=True)
        with sc4:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Lines Covered</div><div class='kpi-value'>{assigned_lines} / {total_items_count}</div><div class='kpi-subtext'>Usable qualified lines</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A; margin-bottom:12px;'>Illustrative Price-Only Allocation</div>", unsafe_allow_html=True)

        alloc_col1, alloc_col2 = st.columns([2.2, 1.8])
        with alloc_col1:
            fig = px.bar(
                calc["split_allocation"],
                x="Awarded Supplier",
                y="Extended Spend (INR)",
                color="Awarded Supplier",
                color_discrete_sequence=[
                    DESIGN_SYSTEM["colors"]["accent_primary"],
                    "#10B981",
                    "#F59E0B",
                    "#6366F1",
                    "#94A3B8"
                ],
                template="plotly_white"
            )
            fig.update_layout(height=260, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
        with alloc_col2:
            summary_alloc = []
            for sname, count in calc["supplier_allocated_counts"].items():
                spend_val = calc["supplier_allocated_spends"][sname]
                summary_alloc.append({
                    "Supplier": sname,
                    "Allocated SKUs": f"{count} lines",
                    "Extended Spend": f"₹{spend_val:,.2f}"
                })
            if calc["unassigned_count"] > 0:
                summary_alloc.append({
                    "Supplier": "Unassigned",
                    "Allocated SKUs": f"{calc['unassigned_count']} lines",
                    "Extended Spend": "—"
                })
            st.dataframe(pd.DataFrame(summary_alloc), use_container_width=True, hide_index=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # 6. Decision Readiness Framework (Before Issuing PO)
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Decision Readiness</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>The current dataset supports a price-only comparison. Final award execution requires resolution of the pre-requisite items below.</div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background-color: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 6px; padding: 14px 18px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.82rem; font-weight: 700; color: #0369A1; text-transform: uppercase; letter-spacing: 0.04em;">
                    PRICE-ONLY SCENARIO READY
                </span>
                <span class="badge-base badge-normalized">PRE-AWARD VALIDATION</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>BEFORE ISSUING A PURCHASE ORDER:</div>", unsafe_allow_html=True)
        
        dr_col1, dr_col2 = st.columns(2)
        with dr_col1:
            st.markdown(f"<div class='decision-list-item'><span style='color:#B45309; font-weight:700;'>1. Resolve Quote Exceptions:</span> Audit and verify {calc['total_line_exceptions']} pending Review Required / unquoted lines.</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'><span style='color:#B45309; font-weight:700;'>2. Confirm GST Percentage:</span> Collect numerical GST rates for tax amount calculation.</div>", unsafe_allow_html=True)
        with dr_col2:
            st.markdown("<div class='decision-list-item'><span style='color:#B45309; font-weight:700;'>3. Confirm Freight Amounts:</span> Obtain exact freight costs for Buyer Collect suppliers (BoxCraft & National).</div>", unsafe_allow_html=True)
            st.markdown("<div class='decision-list-item'><span style='color:#B45309; font-weight:700;'>4. Validate Capacity Schedule:</span> Verify monthly capacity against target delivery timelines.</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # 7. Collapsible Executive Drawers
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Methodology, Assumptions & Audit Trail</div>", unsafe_allow_html=True)
        
        with st.expander("Decision Considerations & Trade-Offs"):
            if st.session_state.last_analysis_result and st.session_state.last_analysis_result.get("trade_offs"):
                for to in st.session_state.last_analysis_result["trade_offs"]:
                    st.markdown(f"• {to}")
            else:
                st.markdown("• Multi-supplier split allocations increase purchase order administrative overhead.")
                st.markdown("• Lower-priced suppliers may have tighter production capacity constraints during peak season.")

        with st.expander("Data Gaps & Assumptions"):
            if st.session_state.last_analysis_result and st.session_state.last_analysis_result.get("data_gaps"):
                for dg in st.session_state.last_analysis_result["data_gaps"]:
                    st.markdown(f"• {dg}")
            else:
                st.markdown("• Numerical GST percentage rates are missing from supplier submissions.")
                st.markdown("• Freight cost amounts are missing for non-DDP suppliers.")

        with st.expander("Calculation Methodology Basis"):
            m_c1, m_c2 = st.columns(2)
            with m_c1:
                st.markdown("**INCLUDED IN THIS CALCULATION:**")
                st.markdown("✓ Normalized unit prices (INR / requested UOM)")
                st.markdown("✓ Requested RFQ quantities & SKU specs")
                st.markdown("✓ Mandatory qualification status (ISO 9001 + Defect rate + ESG)")
                st.markdown("✓ Usable quote coverage")
            with m_c2:
                st.markdown("**EXCLUDED FROM THIS CALCULATION:**")
                st.markdown("— GST rates & numerical tax amounts")
                st.markdown("— Freight cost amounts")
                st.markdown("— Lead time & delivery schedule buffer")
                st.markdown("— Capacity sufficiency over fulfillment period")

        with st.expander("Evidence & Audit Trail Export"):
            st.markdown("Supplier-line records available for audit export. Exports include original quote, normalized price, validation status, extraction confidence, source reference, and RFQ fingerprint.")
            
            current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "N/A") if st.session_state.rfq_data else "N/A"
            audit_export_rows = []
            
            for idx, row in st.session_state.master_matrix.iterrows():
                for sname in calc["active_suppliers"]:
                    meta = SUPPLIER_MAP[sname]
                    raw_src = row.get(meta["source_col"])
                    clean_src = raw_src if (raw_src and pd.notna(raw_src) and str(raw_src).strip()) else "Source Reference Unavailable"
                    snip_src = row.get(meta["snippet_col"], "No snippet available.")
                    
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
                        "Target Price (INR)": row.get("Target Price (INR)", "—"),
                        "Est Extended Spend": row.get("Est Extended Spend", "—"),
                        "Supplier": sname,
                        "Original Quote": row.get(meta["orig_col"], "—"),
                        "Normalized Unit Price (INR)": row.get(meta["norm_col"], "—"),
                        "Validation Status": row.get(meta["status_col"], "—"),
                        "Extraction confidence": row.get(meta["conf_col"], "—"),
                        "Source": clean_src,
                        "Verbatim Snippet": snip_src,
                        "Source Type": "Supplier Submitted" if is_submitted else "Demo Baseline",
                        "Quote Version Status": q_ver_status,
                        "RFQ Fingerprint": current_rfq_fp,
                        "Qualification Status": "Qualified" if calc["qualification_status"][sname]["qualified"] else "Disqualified"
                    })
                    
            audit_csv_data = pd.DataFrame(audit_export_rows).to_csv(index=False).encode('utf-8')
            st.download_button("Download comparison & audit CSV", audit_csv_data, "RFQ_Audit_Master_Matrix.csv", "text/csv", type="secondary")

        st.markdown("</div>", unsafe_allow_html=True)
