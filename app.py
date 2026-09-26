import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
import datetime
import random
import plotly.express as px
import plotly.graph_objects as go
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
DEMO_FX_RATES = {
    "USD": 83.50,
    "EUR": 90.20,
    "INR": 1.00
}

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
        "installation_visible": False,
        "sample_prompts": [
            "Which supplier is lowest cost for 5-ply cartons vs 3-ply cartons?",
            "Show me suppliers with missing ISO certifications and unquoted SKUs.",
            "What is the financial savings if we award Apex for Bhiwandi and CorruSeal for Hosur?",
            "Identify line items where prices deviate by more than 20% across vendors.",
            "Which vendor offers the best overall lead time and payment terms combination?",
            "Show total spend if we exclude disqualified vendors from the split scenario."
        ]
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
        "installation_default": "Vendor Included",
        "sample_prompts": [
            "Which furniture vendor includes full installation with a 3-year warranty?",
            "Compare ergonomic chair unit prices across all 5 vendors.",
            "What is the cost impact of currency conversion on imported Herman Miller items?",
            "Which vendor has unquoted items or non-standard payment terms?",
            "What if we split workstations to Featherlite and executive chairs to Godrej?",
            "Summarize warranty risks and lead-time bottlenecks for this RFQ."
        ]
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
        "installation_visible": False,
        "sample_prompts": [
            "Which chemical supplier meets the mandatory ESG and ISO requirements?",
            "Normalize prices quoted in USD per metric ton vs INR per kg.",
            "Who is the lowest bidder for bulk raw materials including freight?",
            "Highlight suppliers with defect rates exceeding the 0.5% limit.",
            "What is the optimal split allocation considering vendor monthly capacity?",
            "Show all line items with alternative unit-of-measure quotes."
        ]
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
        "installation_visible": False,
        "sample_prompts": [
            "Which hardware vendor offers the lowest total cost including extended warranty?",
            "Identify USD vs INR quote discrepancies across laptop and server SKUs.",
            "Which suppliers failed to quote on peripheral accessories?",
            "What is the split-award savings if Dell takes servers and HP takes laptops?",
            "Show vendors with payment terms shorter than Net 45 Days.",
            "Evaluate delivery risk based on historical on-time delivery percentages."
        ]
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
            "snippet_col": f"{clean_prefix}_Snippet",
            "uom_col": f"{clean_prefix}_Quoted_UOM",
            "curr_col": f"{clean_prefix}_Currency"
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

    .workflow-stepper-container {{
        background-color: transparent;
        padding: 0;
        margin-bottom: 24px;
        border-bottom: 1px solid {DESIGN_SYSTEM['colors']['border_subtle']};
        padding-bottom: 16px;
    }}

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

    .section-divider {{
        height: 1px;
        background-color: {DESIGN_SYSTEM['colors']['border_subtle']};
        margin: 20px 0;
    }}
    </style>
""", unsafe_allow_html=True)

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
    
    random.seed(42)
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
            
            is_missing = False
            curr = "INR"
            uom_str = it['UOM']
            
            if s_idx == 3 and idx in [5, 15, 30]:
                is_missing = True
            elif s_idx == 5 and idx % 7 == 0:
                is_missing = True
                
            if not is_missing:
                price_mult = 0.88 + ((idx * 3 + s_idx * 7) % 30) / 100.0
                base_inr = target_p * price_mult
                
                if s_idx == 2 and idx % 3 == 0:
                    curr = "USD"
                    quoted_p = round(base_inr / DEMO_FX_RATES["USD"], 2)
                    norm_inr = round(quoted_p * DEMO_FX_RATES["USD"], 2)
                    orig_str = f"${quoted_p:.2f} / {uom_str}"
                    snippet_str = f"Quoted in USD (${quoted_p:.2f}/{uom_str}). Converted at 83.50 FX rate."
                elif s_idx == 4 and idx % 4 == 0 and "pcs" in it['UOM']:
                    uom_str = "pack of 10"
                    quoted_p = round(base_inr * 10.0, 2)
                    norm_inr = round(quoted_p / 10.0, 2)
                    orig_str = f"₹{quoted_p:.2f} / {uom_str}"
                    snippet_str = f"Quoted ₹{quoted_p:.2f} per pack of 10. Normalized to ₹{norm_inr:.2f}/pc."
                else:
                    quoted_p = round(base_inr, 2)
                    norm_inr = quoted_p
                    orig_str = f"₹{quoted_p:.2f} / {uom_str}"
                    snippet_str = f"Quoted ₹{quoted_p:.2f} per {uom_str}."

                row_dict[m["orig_col"]] = orig_str
                row_dict[m["norm_col"]] = norm_inr
                row_dict[m["status_col"]] = "CONFIRMED"
                row_dict[m["conf_col"]] = "98%"
                row_dict[m["source_col"]] = f"Quotation Doc · Page {(idx % 3) + 1}"
                row_dict[m["snippet_col"]] = snippet_str
                row_dict[m["uom_col"]] = uom_str
                row_dict[m["curr_col"]] = curr
            else:
                row_dict[m["orig_col"]] = "NO BID"
                row_dict[m["norm_col"]] = None
                row_dict[m["status_col"]] = "MISSING"
                row_dict[m["conf_col"]] = "—"
                row_dict[m["source_col"]] = "Not quoted in proposal"
                row_dict[m["snippet_col"]] = "Item not listed in supplier bid schedule."
                row_dict[m["uom_col"]] = "—"
                row_dict[m["curr_col"]] = "—"

        master.append(row_dict)
    return pd.DataFrame(master)

def get_questionnaire_master_dataset():
    active_sups = get_active_suppliers()
    category = st.session_state.rfq_data.get("category", "Packaging Materials") if st.session_state.get("rfq_data") else "Packaging Materials"

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
            "YES" if idx != 4 else "NO (Expired)",
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
    st.session_state.rfq_data = None

if "responses_unlocked" not in st.session_state:
    st.session_state.responses_unlocked = False

if "compare_unlocked" not in st.session_state:
    st.session_state.compare_unlocked = False

if "uploaded_suppliers" not in st.session_state:
    st.session_state.uploaded_suppliers = set()

if "supplier_meta" not in st.session_state:
    st.session_state.supplier_meta = {}

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

if "user_prompt_input" not in st.session_state:
    st.session_state.user_prompt_input = ""

def sync_rfq_to_master_matrix():
    if st.session_state.rfq_data is None:
        return
    st.session_state.master_matrix = get_supplier_prefabricated_dataset()
    st.session_state.questionnaire_matrix = get_questionnaire_master_dataset()

def reset_rfq_session():
    st.session_state.rfq_data = None
    st.session_state.rfq_status = "Draft"
    st.session_state.user_prompt_input = ""
    if "procurement_brief_textarea" in st.session_state:
        del st.session_state["procurement_brief_textarea"]
    st.session_state.responses_unlocked = False
    st.session_state.compare_unlocked = False
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
# DYNAMIC RULE-BASED QUALIFICATION & QUALIFIED-ONLY SPEND ENGINE
# =============================================================================
def calculate_deterministic_spend_engine(df, quest_df, uploaded_suppliers_set, is_demo_mode):
    active_suppliers = get_active_suppliers()
    sup_map = get_supplier_mapping(active_suppliers)
    
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
                
            is_iso_valid = (not req_iso) or ("YES" in iso_val)
            is_esg_valid = (not req_esg) or ("YES" in esg_val)
            is_defect_valid = (defect_num <= max_defect_thresh)
            
            is_qualified = is_iso_valid and is_esg_valid and is_defect_valid
            
            reasons = []
            if req_iso and not is_iso_valid:
                reasons.append("ISO 9001 missing/expired")
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
    for sname in active_eval_suppliers:
        meta = sup_map[sname]
        norm_col = meta["norm_col"]
        status_col = meta["status_col"]
        
        if norm_col not in df.columns:
            continue
            
        usable_rows = df[df[norm_col].notnull() & df[status_col].isin(["CONFIRMED", "NORMALIZED"])]
        lines_quoted = len(df[df[norm_col].notnull()])
        lines_usable = len(usable_rows)
        has_missing = (df[status_col] == "MISSING").any() or (lines_quoted < len(df))
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
            "qualified": is_qual,
            "col_name": norm_col,
            "status_col": status_col
        }

    # Strict Filtering: Only Qualified Vendors can win line awards
    qualified_complete = {
        k: v["total_spend"] for k, v in supplier_totals.items() 
        if v["qualified"] and v["is_complete"]
    }
    
    if qualified_complete:
        best_single_name = min(qualified_complete, key=qualified_complete.get)
        best_single_spend = qualified_complete[best_single_name]
        has_complete_option = True
    else:
        best_single_name = "None (Disqualified or Partial)"
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
    vendor_award_summary = {sname: {"spend": 0.0, "lines": 0} for sname in qual_cols.keys()}
    
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
            vendor_award_summary[cheapest_supplier]["spend"] += line_total
            vendor_award_summary[cheapest_supplier]["lines"] += 1
        else:
            cheapest_supplier = "Unassigned / Disqualified"
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
        "vendor_award_summary": vendor_award_summary,
        "unassigned_count": unassigned_count,
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

if st.session_state.pending_extraction:
    pending_vendor = st.session_state.pending_extraction.get("supplier", "Vendor")
    st.warning(f"⚠️ **Pending Extraction Review:** Extracted quote data for **{pending_vendor}** has not yet been added to the comparison matrix. Please apply or discard the extracted quote below before proceeding.")

stages = [
    ("Create RFQ", "01 Create RFQ", True),
    ("Supplier Responses", "02 Response Audit & Ingestion Workspace", st.session_state.responses_unlocked),
    ("Compare & Decide", "03 Compare & Decide Workspace", st.session_state.compare_unlocked and not st.session_state.pending_extraction)
]
cur_idx = [s[0] for s in stages].index(st.session_state.stage)

st.markdown("<div class='workflow-stepper-container'>", unsafe_allow_html=True)
step_cols = st.columns(3)
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
    if st.session_state.rfq_data is None:
        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-title'>Turn a sourcing requirement into a structured RFQ</div>", unsafe_allow_html=True)
            st.markdown("<div class='section-header-subtitle'>Describe what you're buying, where it is needed, quantities, delivery expectations and any commercial constraints. AI will turn this into an editable RFQ draft.</div>", unsafe_allow_html=True)

            def set_packaging_brief():
                st.session_state["procurement_brief_textarea"] = "Source 30 corrugated packaging box SKUs for Bhiwandi and Hosur logistics facilities with Net 60 payment terms, 60 days price validity, and ISO 9001 mandatory certification."
                st.session_state.user_prompt_input = st.session_state["procurement_brief_textarea"]

            def set_furniture_brief():
                st.session_state["procurement_brief_textarea"] = "Create an RFQ for executive office furniture, modular workstations, and ergonomic mesh chairs across Corporate HQ, Pune Tech Hub, and regional branch with 3-year comprehensive warranty."
                st.session_state.user_prompt_input = st.session_state["procurement_brief_textarea"]

            def clear_brief():
                st.session_state["procurement_brief_textarea"] = ""
                st.session_state.user_prompt_input = ""

            prompt_val = st.text_area(
                "Procurement Brief:",
                key="procurement_brief_textarea",
                value=st.session_state.get("user_prompt_input", ""),
                height=120,
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

            with p_col2:
                st.button("Try 30-SKU Packaging Brief", type="secondary", on_click=set_packaging_brief, use_container_width=True)

            with p_col3:
                st.button("Try Furniture Brief", type="secondary", on_click=set_furniture_brief, use_container_width=True)

            with p_col4:
                st.button("🔄 Reset prompt", type="secondary", on_click=clear_brief, use_container_width=True)

            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.82rem; font-weight:600; color:#475569; margin-bottom:6px;'>WHAT AI WILL GENERATE:</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.82rem; color:#64748B;'>Category-Aware Scope Overview &nbsp;•&nbsp; Custom SKU Line Items & Target Prices &nbsp;•&nbsp; Relevant Commercial Controls &nbsp;•&nbsp; Contextual Quality Benchmarks</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    else:
        current_cat = st.session_state.rfq_data.get("category", "Packaging Materials")
        cat_meta = CATEGORY_DEFAULTS.get(current_cat, CATEGORY_DEFAULTS["Packaging Materials"])

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

        with st.container():
            st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
            st.markdown(f"<div class='section-header-title'>Line Items ({len(st.session_state.rfq_data['line_items'])} SKUs)</div>", unsafe_allow_html=True)
            
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
                    st.toast("✓ RFQ draft saved successfully!", icon="💾")
            with f3:
                if st.button("Review & Publish RFQ →", type="primary", disabled=has_invalid_qty, use_container_width=True):
                    st.session_state.rfq_status = "Published"
                    st.session_state.responses_unlocked = True
                    st.session_state.stage = "Supplier Responses"
                    scroll_to_top()
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# =============================================================================
# STAGE 2: HIGH-VALUE RESPONSE AUDIT & INGESTION WORKSPACE
# =============================================================================
elif st.session_state.stage == "Supplier Responses":
    active_sups = get_active_suppliers()
    sup_map = get_supplier_mapping(active_sups)

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Response Audit & Ingestion Workspace</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Stage raw vendor files, verify extracted line items, and audit commercial risk factors before committing to decision modeling.</div>", unsafe_allow_html=True)

        resp_col1, resp_col2, resp_col3, resp_col4 = st.columns(4)
        total_sub_count = len(st.session_state.uploaded_suppliers) if not st.session_state.demo_mode else len(active_sups)
        
        with resp_col1:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Submitted Proposals</div><div class='kpi-value'>{total_sub_count} / {len(active_sups)}</div><div class='kpi-subtext'>Vendors responded</div></div>", unsafe_allow_html=True)
        with resp_col2:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Vendors</div><div class='kpi-value' style='color:#166534;'>{calc['total_qualified_suppliers']}</div><div class='kpi-subtext'>Passed compliance</div></div>", unsafe_allow_html=True)
        with resp_col3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Disqualified Vendors</div><div class='kpi-value' style='color:#991B1B;'>{calc['total_disqualified_suppliers']}</div><div class='kpi-subtext'>Failed criteria</div></div>", unsafe_allow_html=True)
        with resp_col4:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Normalization Status</div><div class='kpi-value' style='font-size:1.0rem; color:#0369A1;'>INR (₹83.50/$)</div><div class='kpi-subtext'>Unified FX & UOM</div></div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # PAGE 2 HIGH-VALUE SUB-TABS (Conversion Audit & Commercial Risk)
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        t_ingest, t_audit, t_risk = st.tabs([
            "📥 Document Ingestion & Staging",
            "🔀 Normalization & FX Audit Log",
            "⚠️ Pre-Decision Commercial Risk Matrix"
        ])

        with t_ingest:
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
                        st.warning("⚠ Duplicate file detected. This document has already been processed.")
                    else:
                        status_placeholder = st.empty()
                        status_placeholder.info(f"⏳ Reading raw proposal document for **{supplier_target}**...")
                        
                        try:
                            ext = uploaded_file.name.split(".")[-1].upper()
                            rfq_items_context = [
                                {"Line #": row["Line #"], "Description": row["Description"], "UOM": row["UOM"]}
                                for _, row in st.session_state.master_matrix.iterrows()
                            ]
                            
                            unified_schema_prompt = f"""
                            Extract line item prices for supplier '{supplier_target}' into JSON matching target RFQ SKUs:
                            {json.dumps(rfq_items_context)}

                            Output JSON structure:
                            {{
                               "detected_supplier_header": "string",
                               "supplier": "{supplier_target}",
                               "currency": "INR or USD or EUR",
                               "overall_confidence": "96%",
                               "extracted_prices": [
                                  {{
                                     "line_num": "ITEM-001",
                                     "quoted_price": 22.50,
                                     "currency": "INR or USD",
                                     "quoted_uom": "pcs or pack or set",
                                     "normalization_note": "Converted USD to INR at 83.50 rate" or "Direct INR",
                                     "verbatim_snippet": "string",
                                     "confidence": "98%",
                                     "source_reference": "Page 1"
                                  }}
                               ]
                            }}
                            """
                            
                            raw_doc_text = parse_raw_document_content(file_bytes, uploaded_file.name, uploaded_file.type)
                            res = client.models.generate_content(
                                model="gemini-2.5-flash", 
                                contents=f"Raw Content:\n{raw_doc_text}\n\n{unified_schema_prompt}",
                                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                            )

                            status_placeholder.empty()
                            parsed_ext = extract_json_from_response(res.text)
                            
                            if "extracted_prices" in parsed_ext and len(parsed_ext["extracted_prices"]) > 0:
                                st.session_state.pending_extraction = {
                                    "supplier": supplier_target,
                                    "file_name": uploaded_file.name,
                                    "file_hash": file_hash,
                                    "source_channel": f"{ext} Proposal Upload",
                                    "overall_confidence": parsed_ext.get("overall_confidence", "95%"),
                                    "parsed": parsed_ext
                                }
                                st.success("Extraction complete. Review details below.")
                        except Exception as e:
                            status_placeholder.empty()
                            st.error(f"Extraction failed: {str(e)}")

        with t_audit:
            st.markdown("<div style='font-size:0.88rem; font-weight:600; color:#0F172A;'>Line-Item Extraction & FX Normalization Log</div>", unsafe_allow_html=True)
            st.caption("Verifiable audit trail detailing raw vendor quotes vs. normalized INR rates.")
            
            audit_log_data = []
            for idx, row in st.session_state.master_matrix.iterrows():
                for sname in calc["active_suppliers"]:
                    m = sup_map[sname]
                    raw_q = row.get(m["orig_col"], "NO BID")
                    norm_p = row.get(m["norm_col"])
                    if pd.notnull(norm_p):
                        audit_log_data.append({
                            "Line #": row["Line #"],
                            "Description": row["Description"],
                            "Supplier": sname,
                            "Raw Quoted Rate": raw_q,
                            "Normalized Unit Rate": f"₹{norm_p:.2f}",
                            "Applied FX Rate": "1.0 (INR)" if "$" not in str(raw_q) else "83.50 (USD/INR)",
                            "Extraction Excerpt": row.get(m["snippet_col"], "Direct quote")
                        })
            st.dataframe(pd.DataFrame(audit_log_data), use_container_width=True, height=300, hide_index=True)

        with t_risk:
            st.markdown("<div style='font-size:0.88rem; font-weight:600; color:#0F172A;'>Supplier Compliance & Commercial Deviation Matrix</div>", unsafe_allow_html=True)
            st.caption("Identify non-compliant payment terms, missing certifications, and high defect rates prior to award selection.")
            
            risk_rows = []
            for sname in calc["active_suppliers"]:
                q_info = calc["qualification_status"][sname]
                s_tot = calc["supplier_totals"][sname]
                pay_val = st.session_state.questionnaire_matrix.loc[st.session_state.questionnaire_matrix["Questionnaire Metric"] == "Offered Payment Terms", sname].values[0] if sname in st.session_state.questionnaire_matrix.columns else "Net 60"
                
                risk_rows.append({
                    "Supplier": sname,
                    "Qualification Badge": "QUALIFIED" if q_info["qualified"] else "DISQUALIFIED",
                    "Disqualification Reason": q_info["reason"],
                    "Offered Terms": pay_val,
                    "Commercial Risk": "Low Risk" if "Net 60" in pay_val else "Requires Approval",
                    "SKU Coverage": f"{s_tot['lines_quoted']} / {s_tot['total_lines']} SKUs"
                })
            
            risk_df = pd.DataFrame(risk_rows)
            def style_risk_matrix(df_data):
                styled = pd.DataFrame('', index=df_data.index, columns=df_data.columns)
                for idx, row in df_data.iterrows():
                    if row["Qualification Badge"] == "QUALIFIED":
                        styled.loc[idx, "Qualification Badge"] = 'background-color: #DCFCE7; color: #15803D; font-weight: bold;'
                    else:
                        styled.loc[idx, "Qualification Badge"] = 'background-color: #FEF2F2; color: #991B1B; font-weight: bold;'
                return styled

            st.dataframe(risk_df.style.apply(style_risk_matrix, axis=None), use_container_width=True, hide_index=True)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← Back to Requirements", type="secondary"):
            st.session_state.stage = "Create RFQ"
            scroll_to_top()
            st.rerun()
    with b2:
        if st.button("Continue to Compare & Decide Workspace →", type="primary"):
            st.session_state.compare_unlocked = True
            st.session_state.stage = "Compare & Decide"
            scroll_to_top()
            st.rerun()

# =============================================================================
# STAGE 3: COMPARE & DECIDE WORKSPACE (DYNAMIC PER-QUERY AI)
# =============================================================================
elif st.session_state.stage == "Compare & Decide":
    active_sups = get_active_suppliers()
    sup_map = get_supplier_mapping(active_sups)
    current_cat = st.session_state.rfq_data.get("category", "Packaging Materials") if st.session_state.rfq_data else "Packaging Materials"
    cat_prompts = CATEGORY_DEFAULTS.get(current_cat, CATEGORY_DEFAULTS["Packaging Materials"])["sample_prompts"]

    calc = calculate_deterministic_spend_engine(
        st.session_state.master_matrix,
        st.session_state.questionnaire_matrix,
        st.session_state.uploaded_suppliers,
        st.session_state.demo_mode
    )

    current_dataset_fp = compute_dataset_fingerprint()

    # SECTION A: UNIFIED COMPARISON MATRIX & COLOR-CODED TABLES
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Single Side-by-Side Response Comparison Workspace</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>All supplier responses landed side-by-side: same lines, same units, same currency — with lowest bidder badges and compliance sitting directly alongside the numbers.</div>", unsafe_allow_html=True)

        tab_prices, tab_quest, tab_docs = st.tabs([
            "📊 Line-Item Pricing Matrix & Lowest Bid Highlights", 
            "📋 Supplier Questionnaire & Color-Coded Compliance",
            "📄 Document Evidence & Source Provenance Inspector"
        ])

        with tab_prices:
            matrix_cols = ["Line #", "Description", "Quantity", "UOM", "Target Price (INR)"]
            for sname in calc["active_suppliers"]:
                matrix_cols.append(sup_map[sname]["norm_col"])
                
            matrix_display = st.session_state.master_matrix[matrix_cols].copy()
            
            # Compute Lowest Bidder per Line Item
            lowest_bidders = []
            lowest_prices = []
            for idx, row in matrix_display.iterrows():
                valid_prices = {}
                for sname in calc["active_suppliers"]:
                    c_col = sup_map[sname]["norm_col"]
                    val = row[c_col]
                    if pd.notnull(val) and val > 0:
                        valid_prices[sname] = val
                if valid_prices:
                    best_sup = min(valid_prices, key=valid_prices.get)
                    best_p = valid_prices[best_sup]
                    lowest_bidders.append(best_sup)
                    lowest_prices.append(f"₹{best_p:.2f}")
                else:
                    lowest_bidders.append("No Bids")
                    lowest_prices.append("—")
                    
            matrix_display.insert(5, "Lowest Price Bidder", lowest_bidders)
            matrix_display.insert(6, "Lowest Price (INR)", lowest_prices)

            col_rename_map = {"Quantity": "Qty", "Target Price (INR)": "Target (₹)"}
            for sname in calc["active_suppliers"]:
                col_rename_map[sup_map[sname]["norm_col"]] = f"{sup_map[sname]['prefix'].upper()} (₹)"
            matrix_display = matrix_display.rename(columns=col_rename_map)

            def highlight_lowest_and_missing(df_data):
                styled_df = pd.DataFrame('', index=df_data.index, columns=df_data.columns)
                for idx, row in df_data.iterrows():
                    best_sup = lowest_bidders[idx]
                    if best_sup != "No Bids":
                        best_col_renamed = f"{sup_map[best_sup]['prefix'].upper()} (₹)"
                        if best_col_renamed in df_data.columns:
                            styled_df.loc[idx, best_col_renamed] = 'background-color: #DCFCE7; color: #15803D; font-weight: bold;'
                            styled_df.loc[idx, "Lowest Price Bidder"] = 'background-color: #EFF6FF; color: #1D4ED8; font-weight: bold;'
                    
                    for sname in calc["active_suppliers"]:
                        c_renamed = f"{sup_map[sname]['prefix'].upper()} (₹)"
                        if c_renamed in df_data.columns and pd.isnull(row[c_renamed]):
                            styled_df.loc[idx, c_renamed] = 'background-color: #FEF2F2; color: #991B1B; font-style: italic;'
                return styled_df

            styled_matrix = matrix_display.style.apply(highlight_lowest_and_missing, axis=None).format(
                subset=[f"{sup_map[s]['prefix'].upper()} (₹)" for s in calc["active_suppliers"]],
                formatter=lambda x: f"₹{x:.2f}" if pd.notnull(x) else "NO BID"
            ).format(subset=["Target (₹)"], formatter="₹{:.2f}")

            st.dataframe(styled_matrix, use_container_width=True, height=380, hide_index=True)

        with tab_quest:
            st.markdown("<div style='font-size:0.88rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Qualification & Questionnaire Compliance Matrix</div>", unsafe_allow_html=True)
            quest_df = st.session_state.questionnaire_matrix.copy()

            def style_questionnaire_cells(df_data):
                styled_df = pd.DataFrame('', index=df_data.index, columns=df_data.columns)
                for c in df_data.columns:
                    if c != "Questionnaire Metric":
                        for idx, val in df_data[c].items():
                            v_str = str(val).strip().upper()
                            if "YES" in v_str:
                                styled_df.loc[idx, c] = 'background-color: #DCFCE7; color: #15803D; font-weight: bold;'
                            elif "NO" in v_str or "EXPIRED" in v_str:
                                styled_df.loc[idx, c] = 'background-color: #FEF2F2; color: #991B1B; font-weight: bold;'
                            elif "NET 60" in v_str or "DDP" in v_str:
                                styled_df.loc[idx, c] = 'background-color: #F0F9FF; color: #0369A1;'
                return styled_df

            styled_quest = quest_df.style.apply(style_questionnaire_cells, axis=None)
            st.dataframe(styled_quest, use_container_width=True, height=340, hide_index=True)

        with tab_docs:
            st.markdown("<div style='font-size:0.88rem; font-weight:600; color:#0F172A;'>Attached Document Evidence & Verbatim Provenance</div>", unsafe_allow_html=True)
            doc_col1, doc_col2 = st.columns([1, 2])
            with doc_col1:
                line_select = st.selectbox("Select Line Item to Inspect:", st.session_state.master_matrix["Line #"].tolist())
                line_row = st.session_state.master_matrix[st.session_state.master_matrix["Line #"] == line_select].iloc[0]
                st.markdown(f"**Selected SKU:** `{line_row['Line #']}`")
                st.markdown(f"**Description:** {line_row['Description']}")
                st.markdown(f"**Quantity:** {line_row['Quantity']:,} {line_row['UOM']}")
                st.markdown(f"**Target Unit Price:** ₹{line_row['Target Price (INR)']:.2f}")

            with doc_col2:
                st.markdown("**Side-by-Side Vendor Quotation Excerpts:**")
                p_cols = st.columns(len(calc["active_suppliers"]))
                for idx, sname in enumerate(calc["active_suppliers"]):
                    m = sup_map[sname]
                    with p_cols[idx]:
                        st.markdown(f"**{sname}**")
                        st.markdown(f"Raw Quote: `{line_row.get(m['orig_col'], '—')}`")
                        norm_val = line_row.get(m['norm_col'])
                        st.markdown(f"Normalized: `{f'₹{norm_val:.2f}' if pd.notnull(norm_val) else 'NO BID'}`")
                        st.caption("Source Excerpt:")
                        st.code(line_row.get(m['snippet_col'], "No snippet available."), language="text")

        st.markdown("</div>", unsafe_allow_html=True)

    # SECTION B: DYNAMIC DECISION CO-PILOT WITH QUERY-SPECIFIC ANSWERS
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Procurement Decision & Scenario Co-Pilot</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-header-subtitle'>Contextually tailored questions for <b>{current_cat}</b>. Select a suggested prompt or ask any custom question.</div>", unsafe_allow_html=True)

        st.markdown("<div style='font-size:0.88rem; font-weight:600; color:#0F172A; margin-bottom:8px;'>Suggested Decision Queries:</div>", unsafe_allow_html=True)
        
        prompt_cols = st.columns(2)
        
        for idx, p_text in enumerate(cat_prompts):
            c_idx = idx % 2
            with prompt_cols[c_idx]:
                if st.button(f"💡 {p_text}", key=f"dyn_prompt_btn_{idx}", use_container_width=True):
                    st.session_state.user_prompt_input = p_text

        query_input = st.text_input(
            "Enter sourcing question:",
            key="custom_query_input_text",
            value=st.session_state.get("user_prompt_input", cat_prompts[0]),
            placeholder="e.g. Which supplier is lowest cost for 5-ply cartons vs 3-ply cartons?",
            label_visibility="collapsed"
        )

        if st.button("Ask Decision Co-Pilot →", type="primary"):
            if query_input:
                status_placeholder = st.empty()
                status_placeholder.info(f"⏳ **Analyzing Question:** '{query_input}' against supplier matrix...")

                matrix_json = st.session_state.master_matrix.to_json(orient="records")
                q_json = st.session_state.questionnaire_matrix.to_json(orient="records")
                
                disqualified_list = [f"{s} ({info['reason']})" for s, info in calc['qualification_status'].items() if (s in calc['active_suppliers'] and not info['qualified'])]
                disqual_str = "; ".join(disqualified_list) if disqualified_list else "None"

                system_instruction = f"""
                You are an executive procurement intelligence model.
                You are asked the SPECIFIC question: '{query_input}'.
                
                CRITICAL INSTRUCTIONS:
                1. Do NOT give a standard template response. 
                2. Answer ONLY the specific user question '{query_input}'.
                3. If asked about 5-ply vs 3-ply, filter rows with '5-ply' or '3-ply' and compare prices.
                4. If asked about non-compliant or missing ISO, list the exact suppliers (e.g. National Paper Mills).
                5. Keep output high-density, precise, and structured in JSON.
                
                JSON OUTPUT SCHEME:
                {{
                    "headline_answer": "Direct, single-sentence response answering the exact question with numbers.",
                    "executive_summary": "1-2 bullet points with data facts.",
                    "key_findings": ["Finding 1 addressing specific SKUs/vendors", "Finding 2"],
                    "trade_offs_and_risks": ["Risk 1", "Risk 2"],
                    "recommended_action": "Actionable procurement next step."
                }}
                """
                
                try:
                    res = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=f"Master Matrix:\n{matrix_json}\n\nQuestionnaire:\n{q_json}\n\nUser Question: {query_input}",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                    status_placeholder.empty()
                    parsed_ans = extract_json_from_response(res.text)
                    
                    st.session_state.last_analysis_query = query_input
                    st.session_state.last_analysis_result = parsed_ans
                except Exception as e:
                    status_placeholder.empty()
                    st.error(f"Co-Pilot response error: {str(e)}")

        st.markdown("</div>", unsafe_allow_html=True)

    # SECTION C: HIGH-DENSITY DECISION-READY EXECUTIVE BRIEF
    if st.session_state.last_analysis_result:
        ans = st.session_state.last_analysis_result
        
        with st.container():
            st.markdown("<div class='aerchain-section' style='background-color: #FFFFFF; border: 1px solid #CBD5E1; padding: 20px; border-radius: 8px;'>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:0.80rem; font-weight:700; color:#2563EB; text-transform:uppercase; letter-spacing:0.05em;'>Executive Decision Brief</div>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='margin: 4px 0 12px 0; font-size: 1.15rem; font-weight: 700; color: #0F172A;'>{ans.get('headline_answer', '')}</h3>", unsafe_allow_html=True)
            
            k_col1, k_col2 = st.columns(2)
            with k_col1:
                st.markdown("**Key Query Insights:**")
                for item in ans.get("key_findings", []):
                    st.markdown(f"• {item}")
            with k_col2:
                st.markdown("**Trade-offs & Operational Risks:**")
                for item in ans.get("trade_offs_and_risks", []):
                    st.markdown(f"⚠️ {item}")

            st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
            st.markdown(f"**💡 Recommended Action:** {ans.get('recommended_action', 'Proceed with award negotiation.')}")

            st.markdown("</div>", unsafe_allow_html=True)

    # QUALIFIED-ONLY PRICE MODELING & ENHANCED CHART REPRESENTATION
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Price-Only Award Scenario Modeling (Qualified Bidders Only)</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-subtitle'>Excludes disqualified or non-compliant suppliers. Evaluates optimal split allocation across eligible vendors.</div>", unsafe_allow_html=True)

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Qualified Split Spend</div><div class='kpi-value'>₹{calc['split_spend']:,.2f}</div><div class='kpi-subtext'>Optimal line-item allocation</div></div>", unsafe_allow_html=True)
        with sc2:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Lowest Qualified Single Quote</div><div class='kpi-value'>₹{calc['best_single_spend']:,.2f}</div><div class='kpi-subtext'>{calc['best_single_name']}</div></div>", unsafe_allow_html=True)
        with sc3:
            st.markdown(f"<div class='kpi-card'><div class='kpi-label'>Eligible Bidders</div><div class='kpi-value'>{calc['total_qualified_suppliers']} / {len(calc['active_suppliers'])}</div><div class='kpi-subtext'>{calc['total_disqualified_suppliers']} disqualified</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        
        # Enhanced Stacked Bar Chart: Awarded Spend & Line Count per Qualified Vendor
        chart_data = []
        for sname, s_info in calc["vendor_award_summary"].items():
            if s_info["lines"] > 0:
                chart_data.append({
                    "Qualified Supplier": sname,
                    "Awarded Extended Spend (INR)": round(s_info["spend"], 2),
                    "SKU Lines Awarded": s_info["lines"]
                })
        
        if chart_data:
            chart_df = pd.DataFrame(chart_data)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=chart_df["Qualified Supplier"],
                y=chart_df["Awarded Extended Spend (INR)"],
                name="Awarded Spend (INR)",
                marker_color=DESIGN_SYSTEM["colors"]["accent_primary"],
                text=chart_df["Awarded Extended Spend (INR)"].apply(lambda x: f"₹{x:,.0f}"),
                textposition="auto"
            ))
            fig.update_layout(
                title="Optimal Split-Award Distribution Across Qualified Suppliers",
                xaxis_title="Qualified Vendor",
                yaxis_title="Total Awarded Spend (INR)",
                template="plotly_white",
                height=300,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No qualified vendors are currently eligible for line item awards.")

        st.markdown("</div>", unsafe_allow_html=True)

    # Methodology, Assumptions & Audit Trail Export
    with st.container():
        st.markdown("<div class='aerchain-section'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header-title'>Methodology, Assumptions & Audit Trail Export</div>", unsafe_allow_html=True)
        
        with st.expander("Evidence & Audit Trail Export"):
            st.markdown("Supplier-line records available for audit export.")
            current_rfq_fp = st.session_state.rfq_data.get("rfq_fingerprint", "N/A") if st.session_state.rfq_data else "N/A"
            audit_export_rows = []
            
            for idx, row in st.session_state.master_matrix.iterrows():
                for sname in calc["active_suppliers"]:
                    meta = calc["supplier_map"][sname]
                    audit_export_rows.append({
                        "Line #": row["Line #"],
                        "Description": row["Description"],
                        "Quantity": row["Quantity"],
                        "UOM": row["UOM"],
                        "Supplier": sname,
                        "Original Quote": row.get(meta["orig_col"], "—"),
                        "Normalized Unit Price (INR)": row.get(meta["norm_col"], "—"),
                        "Qualification Status": "Qualified" if calc["qualification_status"][sname]["qualified"] else "Disqualified"
                    })
                    
            audit_csv_data = pd.DataFrame(audit_export_rows).to_csv(index=False).encode('utf-8')
            st.download_button("Download comparison & audit CSV", audit_csv_data, "RFQ_Audit_Master_Matrix.csv", "text/csv", type="secondary")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
    cb1, cb2 = st.columns([1, 1])
    with cb1:
        if st.button("← Back to Responses", type="secondary"):
            st.session_state.stage = "Supplier Responses"
            scroll_to_top()
            st.rerun()
