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

# Dynamic Category Commercial & Qualification Defaults
CATEGORY_DEFAULTS = {
    "Packaging Materials": {
        "suppliers": ["Apex Packaging", "BoxCraft Ltd", "CorruSeal Global", "National Paper Mills", "PackTech Solutions"],
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
        "suppliers": ["Godrej Interio", "Featherlite Furniture", "Herman Miller India", "Durian Commercial", "Wipro Furniture"],
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
        "suppliers": ["Sigma Chemical Co", "BASF India", "Reliance Chemicals", "Tata Chemicals", "Aarti Industries"],
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
        "suppliers": ["Dell Enterprise", "HP Commercial Solutions", "Lenovo Global", "Cisco Systems", "Apple Enterprise"],
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
        "suppliers": ["BlueDart Express", "DHL Supply Chain", "Mahindra Logistics", "TCI Freight", "Delhivery Enterprise"],
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

def get_active_suppliers():
    if st.session_state.get("rfq_data") and "category" in st.session_state.rfq_data:
        cat = st.session_state.rfq_data["category"]
        return CATEGORY_DEFAULTS.get(cat, CATEGORY_DEFAULTS["Packaging Materials"])["suppliers"]
    return CATEGORY_DEFAULTS["Packaging Materials"]["suppliers"]

def get_supplier_mapping(suppliers_list):
    s_map = {}
    for sname in suppliers_list:
        clean_prefix = re.sub(r'[^a-zA-Z0-9]', '', sname.split()[0])
        s_map[sname] = {
            "prefix": clean_prefix,
            "orig_col": f"{clean_prefix}_Orig_Price",
            "norm_col": f"{clean_prefix}_Norm_INR",
            "status_col": f"{clean_prefix}_Status",
            "conf_col": f"{clean_prefix}_Confidence",
            "source_col": f"{clean_prefix}_Source_Ref",
            "snippet_col": f"{clean_prefix}_Snippet"
        }
    return s_map

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
    /* GLOBAL RESETS & TYPOGRAPHY */
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

    /* APP SHELL & PRODUCT HEADER */
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

    /* WORKFLOW STEPPER BAR */
    .workflow-stepper-container {{
        background-color: transparent;
        padding: 0;
        margin-bottom: 24px;
        border-bottom: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        padding-bottom: 16px;
    }}

    /* WORKSPACE SECTIONS */
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

    /* METRIC & KPI CARDS */
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

    /* BADGES */
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

    /* BUTTONS */
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

# Multi-Frame Scroll-to-Top Engine
def scroll_to_top():
    st.components.v1.html(
        """
        <script>
            function forceScrollTop() {
                try { window.scrollTo(0, 0); } catch(e) {}
                try { window.parent.scrollTo(0, 0); } catch(e) {}
                try { window.top.scrollTo(0, 0); } catch(e) {}
                try {
                    var doc = window.parent.document;
                    if (doc) {
                        doc.documentElement.scrollTop = 0;
                        doc.body.scrollTop = 0;
                        var mainElem = doc.querySelector('.main');
                        if (mainElem) { mainElem.scrollTop = 0; }
                        var blockContainer = doc.querySelector('.block-container');
                        if (blockContainer) { blockContainer.scrollTop = 0; }
                    }
                } catch(e) {}
            }
            forceScrollTop();
            setTimeout(forceScrollTop, 50);
            setTimeout(forceScrollTop, 150);
            setTimeout(forceScrollTop, 300);
            setTimeout(forceScrollTop, 500);
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

def get_furniture_6_items():
    furn_specs = [
        ("Executive Desk", "Teak Finish, Wire Management, 1800x900mm", 15, "pcs", "Corporate HQ", 28500.00),
        ("Modular Workstation", "4-Seater Linear, Acoustic Partition, Power Popups", 45, "set", "Tech Hub - Pune", 42000.00),
        ("Ergonomic Mesh Chair", "High Back, Lumbar Support, 3D Armrest, Synchro Mechanism", 180, "pcs", "All 3 Locations", 8500.00),
        ("Conference Meeting Table", "12-Seater Modular, Veneer Top, Built-in AV Box", 4, "pcs", "Corporate HQ & Tech Hub", 75000.00),
        ("Visitor Reception Chair", "Mid Back, Leatherette, Cantilever Chrome Base", 60, "pcs", "All 3 Locations", 4200.00),
        ("Full Height Storage Cabinet", "Laminated Wooden, Locking System, Adjustable Shelves", 35, "pcs", "All 3 Locations", 14500.00)
    ]
    items = []
    for idx, (title, spec, qty, uom, loc, target_price) in enumerate(furn_specs, start=1):
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
    if st.session_state.get("rfq_data") and st.session_state.rfq_data.get("line_items"):
        items = st.session_state.rfq_data["line_items"]
    else:
        items = get_canonical_30_items()
        
    active_sups = get_active_suppliers()
    sup_map = get_supplier_mapping(active_sups)
    
    master = []
    for idx, it in enumerate(items, start=1):
        target_p = float(it.get("Target Price (INR)", 25.0))
        
        row_dict = {
            "Line #": it["Line #"],
            "Description": it["Description"],
            "Specification": it["Specification"],
            "Quantity": it["Quantity"],
            "UOM": it["UOM"],
            "Delivery Location": it["Delivery Location"],
            "Target Price (INR)": target_p,
            "Est Extended Spend": round(it["Quantity"] * target_p, 2)
        }
        
        for s_idx, sname in enumerate(active_sups, start=1):
            m = sup_map[sname]
            mult = 0.92 + (s_idx * 0.03) + ((idx % 3) * 0.02)
            p_val = round(target_p * mult, 2)
            
            row_dict[m["orig_col"]] = f"₹{p_val:.2f} / {it['UOM']}"
            row_dict[m["norm_col"]] = p_val
            row_dict[m["status_col"]] = "CONFIRMED"
            row_dict[m["conf_col"]] = "98%"
            row_dict[m["source_col"]] = f"Commercial Proposal · Section {s_idx}"
            row_dict[m["snippet_col"]] = f"{it['Description']} rate quoted at ₹{p_val:.2f} per {it['UOM']}."
            
        master.append(row_dict)
    return pd.DataFrame(master)

def get_questionnaire_master_dataset():
    active_sups = get_active_suppliers()
    category = st.session_state.rfq_data.get("category", "Packaging Materials") if st.session_state.get("rfq_data") else "Packaging Materials"

    # Contextual dynamic attributes per supplier
    dynamic_pay_terms = ["Net 60 Days", "Net 30 Days", "30% Advance, 70% Post-Installation", "Net 45 Days", "Net 30 Days"]
    dynamic_capacities = ["1.5M units", "800k units", "2.1M units", "1.1M units", "900k units"] if "Packaging" in category else ["800 units/mo", "500 units/mo", "1,200 units/mo", "650 units/mo", "400 units/mo"]
    
    data = {
        "Questionnaire Metric": [
            "ISO 9001 Certification Attached?",
            "FSC Certification Attached?",
            "ESG Audit Certified?",
            "3-Year Reported Defect Rate",
            "Monthly Capacity",
            "Historical On-Time Delivery (OTD %)",
            "Offered Payment Terms",
            "Freight Responsibility",
            "GST Registration Verified?",
            "Manufacturing Location"
        ]
    }
    for idx, sname in enumerate(active_sups, start=1):
        data[sname] = [
            "YES" if idx != 4 else "NO",
            "YES" if idx % 2 == 1 else "NO",
            "YES" if idx <= 3 else "NO",
            f"0.{idx*2}%",
            dynamic_capacities[(idx-1) % len(dynamic_capacities)],
            f"{99 - idx}.5%",
            dynamic_pay_terms[(idx-1) % len(dynamic_pay_terms)],
            "Supplier Prepaid (DDP)" if idx % 2 != 0 else "Ex-Works",
            "YES",
            f"Facility Hub #{idx}"
        ]
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

if "supplier_meta" not in st.session_state:
    st.session_state.supplier_meta = {}  # Metadata map storing source, filename, confidence per supplier

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
    st.session_state.master_matrix = get_supplier_prefabricated_dataset()
    st.session_state.questionnaire_matrix = get_questionnaire_master_dataset()

def reset_rfq_session():
    st.session_state.rfq_data = None
    st.session_state.rfq_status = "Draft"
    st.session_state.user_prompt_input = ""
    st.session_state.responses_unlocked = False
    st.session_state.compare_unlocked = False
    st.session_state.analyze_unlocked = False
    st.session_state.uploaded_suppliers = set()
    st.session_state.supplier_meta = {}
    st.session_state.supplier_quote_fingerprints = {}
    st.session_state.processed_file_hashes = set()
    st.session_state.pending_extraction = None
    st.session_state.master_matrix = get_supplier_prefabricated_dataset()
    st.session_state.questionnaire_matrix = get_questionnaire_master_dataset()
    invalidate_analysis_snapshot()

sync_rfq_to_master_matrix()

# =============================================================================
# DYNAMIC RULE-BASED QUALIFICATION & SPEND ENGINE
# =============================================================================
def calculate_deterministic_spend_engine(df, quest_df, uploaded_suppliers_set, is_demo_mode):
    active_suppliers = get_active_suppliers()
    sup_map = get_supplier_mapping(active_suppliers)
    current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "") if st.session_state.rfq_data else ""
    
    if is_demo_mode:
        active_eval_suppliers = active_suppliers
    else:
        active_eval_suppliers = [s for s in active_suppliers if s in uploaded_suppliers_set]

    req_iso = st.session_state.rfq_data.get("iso_mandatory", True) if st.session_state.rfq_data else True
    req_esg = st.session_state.rfq_data.get("esg_mandatory", False) if st.session_state.rfq_data else False
    
    defect_str = st.session_state.rfq_data.get("defect_limit", "< 0.5%") if st.session_state.rfq_data else "< 0.5%"
    try:
        max_defect_thresh = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(defect_str))[0])
    except Exception:
        max_defect_thresh = 0.5

    qualification_status = {}
    for sname in active_suppliers:
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
                reasons.append("ISO 9001 missing")
            if req_esg and not is_esg_valid:
                reasons.append("ESG audit missing")
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

    for sname in active_eval_suppliers:
        meta = sup_map[sname]
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
    supplier_allocated_counts = {sname: 0 for sname in active_eval_suppliers if qualification_status[sname]["qualified"]}
    supplier_allocated_spends = {sname: 0.0 for sname in active_eval_suppliers if qualification_status[sname]["qualified"]}
    
    for idx, row in df.iterrows():
        prices = {}
        for sname, col in qual_cols.items():
            if col in df.columns and pd.notnull(row[col]):
                status = str(row.get(sup_map[sname]["status_col"], "")).upper()
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

    total_qualified_suppliers = sum(1 for s in active_eval_suppliers if qualification_status[s]["qualified"])
    total_disqualified_suppliers = sum(1 for s in active_eval_suppliers if not qualification_status[s]["qualified"])

    return {
        "active_suppliers": active_eval_suppliers,
        "supplier_map": sup_map,
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

            prompt_val = st.text_area(
                "Procurement Brief:",
                value=st.session_state.user_prompt_input,
                height=120,
                key="procurement_brief_textarea",
                placeholder="Describe your requirement (e.g., 'Source 30 corrugated packaging SKUs for Bhiwandi and Hosur facilities' or 'Create an RFQ for office furniture across 3 locations')..."
            )
            st.session_state.user_prompt_input = prompt_val
            
            p_col1, p_col2, p_col3, p_col4 = st.columns([1.5, 1, 1, 1])
            is_brief_empty = not prompt_val.strip()
            
            with p_col1:
                if st.button("Generate RFQ draft →", type="primary", disabled=is_brief_empty, use_container_width=True):
                    with st.spinner("Analyzing brief · Extracting specifications · Structuring SKU line items..."):
                        if "furniture" in prompt_val.lower():
                            cat_name = "Office Furniture & Fixtures"
                            c_items = get_furniture_6_items()
                        else:
                            cat_name = "Packaging Materials"
                            c_items = get_canonical_30_items()

                        cat_defaults = CATEGORY_DEFAULTS[cat_name]
                        new_rfq = {
                            "title": f"{cat_name} Sourcing 2026",
                            "category": cat_name,
                            "scope": f"Procurement of {len(c_items)} SKUs.",
                            "delivery_locations": "3 Corporate Logistics Hubs",
                            "payment_terms": cat_defaults["pay_terms"],
                            "price_validity": cat_defaults["validity"],
                            "freight_terms": cat_defaults["freight"],
                            "iso_mandatory": cat_defaults["iso_default"],
                            "fsc_mandatory": cat_defaults.get("fsc_default", False),
                            "esg_mandatory": cat_defaults["esg_default"],
                            "min_capacity": "1.0M units",
                            "target_otd": "95.0%",
                            "defect_limit": "< 0.5%",
                            "incoterms_year": "2020",
                            "aql_benchmark": cat_defaults.get("aql_default", "1.0% AQL"),
                            "sample_required": cat_defaults["sample_req"],
                            "warranty_period": cat_defaults.get("warranty_default", "3 Years"),
                            "installation_required": cat_defaults.get("installation_default", "Vendor Included"),
                            "response_deadline": "15 Oct 2026",
                            "unclear_specs": [
                                {"requirement": "Assembly & Delivery Scope", "finding": "Not specified in brief", "action": "Suggested: Enforce vendor-managed assembly"}
                            ],
                            "line_items": c_items
                        }
                        new_rfq["rfq_fingerprint"] = compute_rfq_fingerprint(new_rfq)
                        st.session_state.rfq_data = new_rfq
                        sync_rfq_to_master_matrix()
                        invalidate_analysis_snapshot()
                        st.session_state.rfq_status = "Draft (AI Generated)"
                        scroll_to_top()
                        st.rerun()

            # "Try Brief" buttons now fill text area and allow user to review before generating
            with p_col2:
                if st.button("Try 30-SKU Packaging Brief", type="secondary", use_container_width=True):
                    st.session_state.user_prompt_input = "Source 30 corrugated packaging box SKUs for Bhiwandi and Hosur logistics facilities with Net 60 payment terms, 60 days price validity, and ISO 9001 mandatory certification."
                    scroll_to_top()
                    st.rerun()

            with p_col3:
                if st.button("Try Furniture Brief", type="secondary", use_container_width=True):
                    st.session_state.user_prompt_input = "Create an RFQ for executive office furniture, modular workstations, and ergonomic mesh chairs across Corporate HQ, Pune Tech Hub, and regional branch with 3-year comprehensive warranty."
                    scroll_to_top()
                    st.rerun()

            with p_col4:
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

        # Process controls state updates FIRST so top KPI summary cards update instantly
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown(f"<div class='section-header-title'>Commercial & Qualification Controls ({current_cat})</div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-subtitle'>Showing parameters relevant to this category requirement. Controls update dynamically.</div>", unsafe_allow_html=True)
            
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

        # Top Summary Cards (Always dynamically up to date with controls)
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
                qual_req_summary = []
                if st.session_state.rfq_data.get('iso_mandatory'): qual_req_summary.append("ISO")
                if st.session_state.rfq_data.get('esg_mandatory'): qual_req_summary.append("ESG")
                qual_str = "+".join(qual_req_summary) if qual_req_summary else "Standard"
                st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualification & Quality</div><div class='kpi-value' style='font-size:0.95rem;'>{qual_str} ({st.session_state.rfq_data.get('defect_limit', '< 0.5%')})</div><div class='kpi-subtext'>{st.session_state.rfq_data.get('freight_terms', 'DDP')}</div></div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        # Actionable Brief Suggestions Engine
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
                            req_title = spec.get("requirement", "").lower()
                            if "installation" in req_title or "assembly" in req_title:
                                st.session_state.rfq_data["installation_required"] = "Vendor Included (Turnkey Enforced)"
                                st.session_state.rfq_data["scope"] += " (Enforcing vendor turnkey installation across all locations)"
                            elif "buffer" in req_title:
                                st.session_state.rfq_data["scope"] += " (Enforcing 10% peak volume buffer)"
                            st.session_state.rfq_data["unclear_specs"] = [s for s in st.session_state.rfq_data["unclear_specs"] if s.get("requirement") != spec.get("requirement")]
                            st.toast(f"✓ Applied parameter directly to RFQ model: {spec.get('requirement')}", icon="✅")
                            st.rerun()
                            
                st.markdown("</div>", unsafe_allow_html=True)

        # Line Items Editor
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
                if st.button("Review & Publish RFQ →", type="primary", disabled=has_invalid_qty, use_container_width=True):
                    st.session_state.show_publish_review_modal = True
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        # Native Streamlit Dialog Modal Popup Window for full Review & Publish (with width="large")
        if st.session_state.get("show_publish_review_modal", False):
            @st.dialog("📋 Executive RFQ Review Before Publishing", width="large")
            def render_publish_review_dialog():
                st.write("Please verify all procurement specifications, applied conditions, and target extended spend before publishing.")
                
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.markdown(f"**Title:** {st.session_state.rfq_data.get('title')}")
                    st.markdown(f"**Category:** {st.session_state.rfq_data.get('category')}")
                    st.markdown(f"**Scope:** {st.session_state.rfq_data.get('scope')}")
                    st.markdown(f"**Delivery Locations:** {st.session_state.rfq_data.get('delivery_locations')}")
                    st.markdown(f"**Response Deadline:** {st.session_state.rfq_data.get('response_deadline')}")
                with m_col2:
                    st.markdown(f"**Payment Terms:** {st.session_state.rfq_data.get('payment_terms')}")
                    st.markdown(f"**Freight Terms:** {st.session_state.rfq_data.get('freight_terms')}")
                    st.markdown(f"**Price Validity:** {st.session_state.rfq_data.get('price_validity')}")
                    st.markdown(f"**ISO 9001 Mandatory:** {'Yes' if st.session_state.rfq_data.get('iso_mandatory') else 'No'}")
                    if st.session_state.rfq_data.get("warranty_period"):
                        st.markdown(f"**Warranty Period:** {st.session_state.rfq_data.get('warranty_period')}")

                st.markdown("---")
                st.markdown("#### SKU Line Items Breakdown")
                preview_df = pd.DataFrame(st.session_state.rfq_data.get("line_items", []))
                st.dataframe(preview_df, use_container_width=True, height=220, hide_index=True)

                tot_budget = sum([it.get('Est Extended Spend', 0.0) for it in st.session_state.rfq_data.get('line_items', [])])
                st.info(f"💰 **Total Target Budget Commitment:** ₹{tot_budget:,.2f} across {len(st.session_state.rfq_data.get('line_items', []))} items.")

                col_d1, col_d2 = st.columns([1, 1])
                with col_d1:
                    if st.button("✏ Edit RFQ Details", type="secondary", use_container_width=True):
                        st.session_state.show_publish_review_modal = False
                        st.rerun()
                with col_d2:
                    if st.button("🚀 Confirm & Publish RFQ Now", type="primary", use_container_width=True):
                        st.session_state.rfq_status = "Published"
                        st.session_state.responses_unlocked = True
                        st.session_state.show_publish_review_modal = False
                        st.session_state.stage = "Supplier Responses"
                        scroll_to_top()
                        st.rerun()

            render_publish_review_dialog()

# =============================================================================
# STAGE 2: SUPPLIER RESPONSES & EXTRACTION
# =============================================================================
elif st.session_state.stage == "Supplier Responses":
    active_sups = get_active_suppliers()
    sup_map = get_supplier_mapping(active_sups)

    # TOP DEMO TOGGLE BAR - Positioned at the very top for real-time visibility
    with st.container():
        st.markdown("<div class='aerchain-section' style='padding-bottom:10px;'>", unsafe_allow_html=True)
        dt_col1, dt_col2 = st.columns([3, 1])
        with dt_col1:
            st.markdown("<div class='section-header-title'>Supplier Response & Submission Workspace</div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-subtitle'>Track supplier quotation submissions, source document channels, extraction confidence, and compliance status.</div>", unsafe_allow_html=True)
        with dt_col2:
            new_demo_mode = st.toggle("Include demo baseline data", value=st.session_state.demo_mode)
            if new_demo_mode != st.session_state.demo_mode:
                st.session_state.demo_mode = new_demo_mode
                invalidate_analysis_snapshot()
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Calculate current state metrics AFTER toggle evaluation
    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    # Dynamic Top KPI Metric Summary Cards
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        resp_col1, resp_col2, resp_col3, resp_col4 = st.columns(4)
        total_sub_count = len(st.session_state.uploaded_suppliers) if not st.session_state.demo_mode else len(active_sups)
        
        with resp_col1:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Submitted Quotes</div><div class='kpi-value'>{total_sub_count} / {len(active_sups)}</div><div class='kpi-subtext'>Vendors responded</div></div>", unsafe_allow_html=True)
        with resp_col2:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Vendors</div><div class='kpi-value' style='color:#166534;'>{calc['total_qualified_suppliers']}</div><div class='kpi-subtext'>Passed compliance</div></div>", unsafe_allow_html=True)
        with resp_col3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Disqualified Vendors</div><div class='kpi-value' style='color:#991B1B;'>{calc['total_disqualified_suppliers']}</div><div class='kpi-subtext'>Failed criteria</div></div>", unsafe_allow_html=True)
        with resp_col4:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Active Category</div><div class='kpi-value' style='font-size:1.0rem;'>{st.session_state.rfq_data.get('category', 'Packaging Materials') if st.session_state.rfq_data else 'Packaging'}</div><div class='kpi-subtext'>{len(st.session_state.master_matrix)} SKUs Total</div></div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # Document Upload & Extraction Workspace
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Add Supplier Quotation Document</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Upload supplier proposal files to automatically extract and normalize line item prices into the comparison matrix.</div>", unsafe_allow_html=True)
        
        up_col1, up_col2 = st.columns([2.5, 1.5])
        with up_col1:
            uploaded_file = st.file_uploader(
                "Drop supplier quotation document (PDF, XLSX, DOCX, JPG, PNG, TXT)",
                type=["pdf", "xlsx", "docx", "png", "jpg", "txt"],
                label_visibility="collapsed"
            )
        with up_col2:
            supplier_target = st.selectbox("Target Supplier:", active_sups)
            if uploaded_file and st.button("Extract quote data", type="primary", use_container_width=True):
                file_bytes = uploaded_file.read()
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                
                if file_hash in st.session_state.processed_file_hashes:
                    st.warning("⚠ Duplicate file detected. This document has already been processed and applied.")
                else:
                    with st.spinner(f"Extracting quotation line items for {supplier_target}..."):
                        try:
                            ext = uploaded_file.name.split(".")[-1].upper()
                            source_channel_name = f"{ext} File Upload"

                            rfq_items_context = [
                                {"Line #": row["Line #"], "Description": row["Description"], "UOM": row["UOM"]}
                                for _, row in st.session_state.master_matrix.iterrows()
                            ]
                            
                            unified_schema_prompt = f"""
                            You are an expert procurement document parser. Extract line item prices for supplier '{supplier_target}' into JSON.
                            Target RFQ SKUs to match against:
                            {json.dumps(rfq_items_context)}

                            INSTRUCTIONS:
                            1. Extract unit prices from the quotation for each line item.
                            2. Match extracted items to the target 'Line #' (e.g. ITEM-001, ITEM-002) based on item description, index order, or SKU codes.
                            3. Output clean JSON matching this exact structure:
                            {{
                               "detected_supplier_header": "string",
                               "supplier": "{supplier_target}",
                               "currency": "INR or USD",
                               "overall_confidence": "96%",
                               "extracted_prices": [
                                  {{
                                     "line_num": "ITEM-001",
                                     "quoted_price": 22.50,
                                     "currency": "INR",
                                     "original_quote_text": "string",
                                     "verbatim_snippet": "string",
                                     "quoted_uom": "pcs or set or box",
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
                                    "source_channel": source_channel_name,
                                    "overall_confidence": parsed_ext.get("overall_confidence", "95%"),
                                    "has_mismatch": has_mismatch,
                                    "detected_vendor": detected_vendor,
                                    "parsed": parsed_ext
                                }
                                st.success("Extraction complete. Review extracted details below.")
                            else:
                                st.error("No structured line-item prices were extracted. Please verify document formatting.")
                        except Exception as e:
                            st.error(f"Could not parse quotation details: {str(e)}")

        if st.session_state.pending_extraction:
            p_data = st.session_state.pending_extraction["parsed"]
            sname = st.session_state.pending_extraction['supplier']
            fname = st.session_state.pending_extraction.get('file_name', 'Quotation Doc')
            s_chan = st.session_state.pending_extraction.get('source_channel', 'Uploaded Document')
            o_conf = st.session_state.pending_extraction.get('overall_confidence', '95%')
            has_mismatch = st.session_state.pending_extraction.get('has_mismatch', False)
            detected_vendor = st.session_state.pending_extraction.get('detected_vendor', '')
            
            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:1.0rem; font-weight:600; color:#0F172A;'>Review Extracted Quote: {sname}</div>", unsafe_allow_html=True)
            st.caption(f"Source: **{s_chan}** ({fname}) • Extraction Confidence: **{o_conf}**")

            confirm_override = True
            if has_mismatch:
                st.warning(f"⚠ **Supplier Identity Mismatch:** Target is **{sname}**, but document indicates **'{detected_vendor}'**.")
                confirm_override = st.checkbox(f"☑ I confirm this document belongs to **{sname}**", value=False)

            valid_rfq_map = {it["Line #"]: it for it in (st.session_state.rfq_data["line_items"] if st.session_state.rfq_data else get_canonical_30_items())}
            review_table = []
            matched_count = 0

            for item in p_data.get("extracted_prices", []):
                lnum = item.get("line_num")
                raw_p = parse_safe_numeric_price(item.get("quoted_price"))
                curr = str(item.get("currency", "INR")).upper()
                q_uom = str(item.get("quoted_uom", "pc")).lower()
                orig_verbatim = item.get("original_quote_text", "")
                verb_snip = item.get("verbatim_snippet", orig_verbatim or "Raw quote excerpt")
                
                if lnum in valid_rfq_map and raw_p:
                    matched_count += 1
                    norm_price = raw_p if curr == "INR" else round(raw_p * DEMO_FX_RATE, 2)
                    review_table.append({
                        "Line #": lnum,
                        "Original Quote": f"₹{raw_p:.2f} / {q_uom}",
                        "Normalized INR": norm_price,
                        "How it was normalized": "Direct INR" if curr == "INR" else "USD → INR Conversion",
                        "Source": item.get("source_reference", "Page 1"),
                        "Verbatim Snippet": verb_snip,
                        "Extraction confidence": item.get("confidence", "95%"),
                        "Validation Status": "CONFIRMED"
                    })

            if review_table:
                st.dataframe(pd.DataFrame(review_table)[["Line #", "Original Quote", "Normalized INR", "How it was normalized", "Source", "Extraction confidence", "Validation Status"]], use_container_width=True, hide_index=True)
            
            rev_col1, rev_col2 = st.columns([1.5, 1])
            with rev_col1:
                if st.button(f"Add {matched_count} extracted values to comparison", type="primary", disabled=(matched_count == 0 or not confirm_override), use_container_width=True):
                    meta = sup_map[sname]
                    for row_entry in review_table:
                        lnum = row_entry["Line #"]
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, meta["norm_col"]] = row_entry["Normalized INR"]
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, meta["orig_col"]] = row_entry["Original Quote"]
                        st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, meta["status_col"]] = "CONFIRMED"
                            
                    st.session_state.uploaded_suppliers.add(sname)
                    st.session_state.supplier_meta[sname] = {
                        "source_channel": s_chan,
                        "file_name": fname,
                        "confidence": o_conf,
                        "timestamp": datetime.datetime.now().strftime("%d %b %H:%M")
                    }
                    st.session_state.pending_extraction = None
                    invalidate_analysis_snapshot()
                    st.toast(f"✓ Added extracted quotes for {sname}", icon="✅")
                    st.rerun()
            with rev_col2:
                if st.button("Discard extraction", type="secondary", use_container_width=True):
                    st.session_state.pending_extraction = None
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # Supplier Response Inbox Table — Dynamic Filtering & Rich Details
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Supplier Response Status Inbox</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Track supplier submission channels, extraction confidence levels, commercial deviations, and qualification badges.</div>", unsafe_allow_html=True)

        if st.session_state.demo_mode:
            display_suppliers = active_sups
        else:
            display_suppliers = [s for s in active_sups if s in st.session_state.uploaded_suppliers]

        if not display_suppliers:
            st.info("ℹ️ **No Supplier Proposals Submitted Yet:** Drop a quotation document above to begin processing supplier bids.")
        else:
            inbox_rows = []
            for sname in display_suppliers:
                info = calc["supplier_totals"].get(sname, {"lines_quoted": 0, "usable_lines": 0, "total_lines": len(st.session_state.master_matrix), "is_complete": False})
                q_info = calc["qualification_status"].get(sname, {"qualified": False, "reason": "Passed"})
                
                coverage = f"{info['lines_quoted']} quoted · {info['usable_lines']} usable / {info['total_lines']} lines"
                qual_str = "Qualified" if q_info["qualified"] else f"Disqualified ({q_info['reason']})"
                
                if sname in st.session_state.uploaded_suppliers and sname in st.session_state.supplier_meta:
                    smeta = st.session_state.supplier_meta[sname]
                    src_channel = smeta["source_channel"]
                    ext_confidence = smeta["confidence"]
                    receipt_str = f"Uploaded ({smeta['timestamp']})"
                elif st.session_state.demo_mode:
                    channels = ["PDF Proposal Upload", "Excel Bid Sheet", "Email Body + Attachment", "Vendor Portal Integration", "PDF Proposal Upload"]
                    confidences = ["98% High", "95% High", "92% Moderate", "99% High", "94% High"]
                    s_idx = active_sups.index(sname) if sname in active_sups else 0
                    src_channel = channels[s_idx % len(channels)]
                    ext_confidence = confidences[s_idx % len(confidences)]
                    receipt_str = "Baseline Loaded"
                else:
                    src_channel = "—"
                    ext_confidence = "—"
                    receipt_str = "Not Submitted"

                pay_terms_val = st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Offered Payment Terms", sname].values[0] if sname in st.session_state.questionnaire_matrix.columns else "Net 60"

                inbox_rows.append({
                    "Supplier Name": sname,
                    "Submission Status": receipt_str,
                    "Source Channel": src_channel,
                    "Extraction Confidence": ext_confidence,
                    "SKU Line Coverage": coverage,
                    "Qualification Status": qual_str,
                    "Offered Payment Terms": pay_terms_val,
                    "Data Quality": "Complete" if info["is_complete"] else "Review Required"
                })
                
            st.dataframe(pd.DataFrame(inbox_rows), use_container_width=True, hide_index=True)
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
    active_sups = get_active_suppliers()
    sup_map = get_supplier_mapping(active_sups)

    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Supplier Pricing & Qualification Matrix</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Compare normalized unit prices, coverage and qualification status for this requirement.</div>", unsafe_allow_html=True)

        calc = calculate_deterministic_spend_engine(
            st.session_state.master_matrix,
            st.session_state.questionnaire_matrix,
            st.session_state.uploaded_suppliers,
            st.session_state.demo_mode
        )

        matrix_cols = ["Line #", "Description", "Quantity", "UOM", "Target Price (INR)"]
        for sname in calc["active_suppliers"]:
            matrix_cols.append(sup_map[sname]["norm_col"])
            
        matrix_display = st.session_state.master_matrix[matrix_cols].copy()
        col_rename_map = {"Quantity": "Qty", "Target Price (INR)": "Target (₹)"}
        for sname in calc["active_suppliers"]:
            col_rename_map[sup_map[sname]["norm_col"]] = sup_map[sname]["prefix"].upper()
        matrix_display = matrix_display.rename(columns=col_rename_map)

        st.dataframe(matrix_display, use_container_width=True, height=380, hide_index=True)
        
        with st.popover("Inspect Document Evidence & Provenance Side-by-Side"):
            st.markdown("<div style='font-size:0.9rem; font-weight:600; color:#0F172A;'>Line-Item Document Evidence Inspector</div>", unsafe_allow_html=True)
            st.caption("Verbatim source excerpts and extraction confidence for active supplier quotes")
            
            line_select = st.selectbox("Select Line Item to Inspect:", st.session_state.master_matrix["Line #"].tolist())
            line_row = st.session_state.master_matrix[st.session_state.master_matrix["Line #"] == line_select].iloc[0]
            
            st.markdown(f"**SKU:** `{line_row['Line #']}` — {line_row['Description']} ({line_row['Quantity']:,} {line_row['UOM']})")
            st.markdown("---")
            
            p_cols = st.columns(len(calc["active_suppliers"]))
            for idx, sname in enumerate(calc["active_suppliers"]):
                m = sup_map[sname]
                with p_cols[idx]:
                    st.markdown(f"**{sname}**")
                    st.markdown(f"Quote: `{line_row.get(m['orig_col'], '—')}`")
                    st.markdown(f"Norm. INR: `₹{line_row.get(m['norm_col'], '—')}`")
                    st.caption("Verbatim Snippet:")
                    st.code(line_row.get(m['snippet_col'], "No snippet available."), language="text")

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
    active_sups = get_active_suppliers()
    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    current_dataset_fp = compute_dataset_fingerprint()

    # 1. Compact Header & Interactive Sourcing Query Bar
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Procurement Decision Workspace</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Analyze supplier eligibility, evaluate price-only split economics, and verify PO pre-requisites.</div>", unsafe_allow_html=True)

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

    # 2. Primary Sourcing Findings Container
    if st.session_state.last_analysis_result:
        parsed_ans = st.session_state.last_analysis_result
        active_intent = parsed_ans.get("intent", "eligibility")
        
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-title'>Primary Sourcing Findings</div>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='margin: 4px 0 16px 0; font-size: 1.15rem; font-weight: 600; color: #0F172A;'>{parsed_ans.get('headline_answer', '')}</h3>", unsafe_allow_html=True)
            
            if active_intent == "eligibility" or "eligib" in st.session_state.last_analysis_query.lower():
                elig_rows = []
                for sname in calc["active_suppliers"]:
                    q_info = calc["qualification_status"][sname]
                    s_info = calc["supplier_totals"][sname]
                    
                    elig_rows.append({
                        "Supplier": sname,
                        "Qualification": "Qualified" if q_info["qualified"] else "Not qualified",
                        "Quote coverage": f"{s_info['lines_quoted']} / {s_info['total_lines']}",
                        "Data status": "Usable" if q_info["qualified"] else f"Excluded ({q_info['reason']})"
                    })
                
                st.dataframe(pd.DataFrame(elig_rows), use_container_width=True, hide_index=True)

            elif active_intent == "landed_cost" or "landed" in st.session_state.last_analysis_query.lower():
                st.warning("Landed cost cannot be calculated due to missing numerical GST rates and freight cost inputs.")

            st.markdown("</div>", unsafe_allow_html=True)

    # 3. Price-Only Allocation Cards & Visual Graph
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Price-Only Sourcing Scenario</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Price-only baseline scenario assuming lowest unit price allocation across qualified suppliers. Freight, GST, capacity, and lead times are excluded.</div>", unsafe_allow_html=True)

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Split Spend</div><div class='kpi-value'>₹{calc['split_spend']:,.2f}</div><div class='kpi-subtext'>Lowest usable allocation</div></div>", unsafe_allow_html=True)
        with sc2:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Lowest Single Quote</div><div class='kpi-value'>₹{calc['best_single_spend']:,.2f}</div><div class='kpi-subtext'>{calc['best_single_name']}</div></div>", unsafe_allow_html=True)
        with sc3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Suppliers</div><div class='kpi-value'>{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}</div><div class='kpi-subtext'>Passed compliance</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
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
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # 4. Methodology, Assumptions & Audit Trail Export
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Methodology, Assumptions & Audit Trail</div>", unsafe_allow_html=True)
        
        with st.expander("Evidence & Audit Trail Export"):
            st.markdown("Supplier-line records available for audit export. Exports include original quote, normalized price, validation status, extraction confidence, source reference, and RFQ fingerprint.")
            
            current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "N/A") if st.session_state.rfq_data else "N/A"
            audit_export_rows = []
            
            for idx, row in st.session_state.master_matrix.iterrows():
                for sname in calc["active_suppliers"]:
                    meta = calc["supplier_map"][sname]
                    raw_src = row.get(meta["source_col"])
                    clean_src = raw_src if (raw_src and pd.notna(raw_src) and str(raw_src).strip()) else "Source Reference Unavailable"
                    snip_src = row.get(meta["snippet_col"], "No snippet available.")

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
                        "RFQ Fingerprint": current_rfq_fp,
                        "Qualification Status": "Qualified" if calc["qualification_status"][sname]["qualified"] else "Disqualified"
                    })
                    
            audit_csv_data = pd.DataFrame(audit_export_rows).to_csv(index=False).encode('utf-8')
            st.download_button("Download comparison & audit CSV", audit_csv_data, "RFQ_Audit_Master_Matrix.csv", "text/csv", type="secondary")

        st.markdown("</div>", unsafe_allow_html=True)
