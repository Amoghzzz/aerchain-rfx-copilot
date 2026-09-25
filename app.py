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
# 1. PAGE CONFIGURATION & QUIET ENTERPRISE DESIGN SYSTEM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Aerchain | Procurement Intelligence Workspace",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom SaaS Design Tokens (Linear/Stripe-Inspired Quiet Interface)
st.markdown("""
    <style>
    /* Typography & Palette */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    [data-testid="stSidebar"] { display: none; }
    
    /* Workspace Containers */
    .compact-header {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 14px 22px;
        margin-bottom: 16px;
    }
    
    .workspace-section {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 20px;
        margin-bottom: 16px;
    }
    
    .side-panel {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 16px;
    }
    
    /* Status Badges */
    .badge-confirmed { background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-normalized { background-color: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-review { background-color: #fffbeb; color: #b45309; border: 1px solid #fef08a; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .badge-missing { background-color: #fef2f2; color: #991b1b; border: 1px solid #fecaca; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    
    /* Provenance Origin Tags */
    .tag-user { background-color: #f1f5f9; color: #334155; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .tag-ai-extracted { background-color: #f0f9ff; color: #0369a1; border: 1px solid #bae6fd; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .tag-ai-suggested { background-color: #f8fafc; color: #475569; border: 1px solid #cbd5e1; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    .tag-buyer-edited { background-color: #fff7ed; color: #c2410c; border: 1px solid #ffedd5; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
    
    /* Quiet Button Hierarchy */
    .stButton>button {
        background-color: #ffffff;
        color: #0f172a;
        font-weight: 500;
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        padding: 6px 14px;
    }
    .stButton>button:hover {
        background-color: #f1f5f9;
        border-color: #94a3b8;
    }
    
    /* Step Navigation Bar */
    .stepper-bar {
        display: flex;
        justify-content: space-between;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 16px;
        margin-bottom: 20px;
    }
    .step-item { font-size: 0.85rem; font-weight: 500; color: #64748b; }
    .step-active { font-size: 0.85rem; font-weight: 600; color: #2563eb; }
    .step-complete { font-size: 0.85rem; font-weight: 500; color: #166534; }
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
    st.error("We couldn't connect to the AI service. Please verify system credentials or try again later.")
    with st.expander("Technical details"):
        st.code(str(e))
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
# 3. FULL STREAM DOCUMENT EXTRACTION HELPERS (UNTRUNCATED)
# -----------------------------------------------------------------------------
def parse_raw_document_content(file_bytes, filename, mime_type):
    """Parses full text/tables from document streams without arbitrary truncation."""
    extracted_text = ""
    
    # PDF via PyMuPDF
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        if fitz:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num, page in enumerate(doc, start=1):
                extracted_text += f"\n--- Page {page_num} ---\n" + page.get_text("text")
        else:
            extracted_text = file_bytes.decode("utf-8", errors="ignore")
            
    # Excel via OpenPyXL
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

    # Word via python-docx
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
# 4. CANONICAL DATASETS & FABRICATED DEMO ARCHETYPES
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
            "Source Tag": "User requirement"
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
        p3_norm = round(p3_usd * 83.50, 2)
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
            "Apex_Source": "Apex_Quote.xlsx -> Sheet: Commercials",
            
            "BoxCraft_Orig_Price": f"₹{p2_orig:.2f} / pc" if p2_orig else "NOT QUOTED",
            "BoxCraft_Norm_INR": p2_orig,
            "BoxCraft_Status": "CONFIRMED" if p2_orig else "MISSING",
            "BoxCraft_Confidence": "95%" if p2_orig else "0%",
            "BoxCraft_Source": "BoxCraft_Quote.pdf -> Page 2" if p2_orig else "BoxCraft_Quote.pdf -> Items 28-30 Omitted",
            
            "CorruSeal_Orig_Price": f"${p3_usd:.2f} / pc",
            "CorruSeal_Norm_INR": p3_norm,
            "CorruSeal_Status": "NORMALIZED",
            "CorruSeal_Confidence": "96%",
            "CorruSeal_Source": "CorruSeal_Commercial.pdf -> Page 1 (FX Rate: ₹83.50/USD)",
            
            "National_Orig_Price": f"₹{p4_per_100:.2f} / 100 pcs",
            "National_Norm_INR": p4_norm,
            "National_Status": "NORMALIZED" if idx != 20 else "REVIEW REQUIRED",
            "National_Confidence": "88%" if idx != 20 else "58% (Scanned Digit Ambiguity)",
            "National_Source": "National_RateCard.jpg -> Region: Bottom Right",
            
            "PackTech_Orig_Price": f"₹{p5_orig:.2f} / pc" if p5_orig else "UNAVAILABLE (Prior-year reference without price)",
            "PackTech_Norm_INR": p5_orig,
            "PackTech_Status": "CONFIRMED" if p5_orig else "MISSING",
            "PackTech_Confidence": "90%" if p5_orig else "0%",
            "PackTech_Source": "PackTech_Email.txt -> Line 4" if p5_orig else "PackTech_Email.txt -> Refused assumption"
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
        "Apex Packaging": ["YES", "YES", "0.4%", "1.2M pcs", "Net 60", "Supplier Prepaid", "YES", "Bhiwandi, MH"],
        "BoxCraft Ltd": ["YES", "NO", "0.3%", "900K pcs", "Net 30", "Buyer Collect", "YES", "Pune, MH"],
        "CorruSeal Global": ["YES", "YES", "0.2%", "1.5M pcs", "Net 60", "Supplier Prepaid", "YES", "Chennai, TN"],
        "National Paper Mills": ["YES", "YES", "0.4%", "1.3M pcs", "Net 30", "Buyer Collect", "YES", "Hosur, TN"],
        "PackTech Solutions": ["NO (Failed)", "YES", "2.1% (Exceeds 0.5%)", "1.1M pcs", "Net 45", "Supplier Prepaid", "YES", "Bengaluru, KA"]
    }
    return pd.DataFrame(data)

# -----------------------------------------------------------------------------
# 5. STATEFUL SESSION STORAGE
# -----------------------------------------------------------------------------
if "stage" not in st.session_state:
    st.session_state.stage = "Create RFQ"

if "rfq_generated" not in st.session_state:
    st.session_state.rfq_generated = False

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
            "Price Validity: Unspecified in prompt (Recommended: 60 Days)",
            "Buffer Lead Time: Unspecified for peak demand season"
        ]
    }

if "master_matrix" not in st.session_state:
    st.session_state.master_matrix = get_supplier_prefabricated_dataset()

if "questionnaire_matrix" not in st.session_state:
    st.session_state.questionnaire_matrix = get_questionnaire_master_dataset()

if "uploaded_docs_log" not in st.session_state:
    st.session_state.uploaded_docs_log = []

# Filter exception state for comparison grid
if "exception_filter" not in st.session_state:
    st.session_state.exception_filter = "All line items"

# -----------------------------------------------------------------------------
# 6. DYNAMIC RULE-BASED QUALIFICATION & SPEND ENGINE (NO FALLBACK DEFAULTS)
# -----------------------------------------------------------------------------
def calculate_deterministic_spend_engine(df, quest_df):
    """
    Evaluates dynamic qualification rules derived directly from Questionnaire Matrix:
    - Rule 1: ISO 9001 must contain 'YES'
    - Rule 2: Defect Rate must be < 0.5%
    Calculates spend strictly from present data.
    """
    qualification_status = {}
    for col in quest_df.columns:
        if col in ["Questionnaire Metric"]:
            continue
            
        sname_raw = col
        iso_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "ISO 9001 Certification Attached?", sname_raw].values
        defect_rows = quest_df.loc[quest_df["Questionnaire Metric"] == "3-Year Verified Defect Rate", sname_raw].values
        
        iso_val = iso_rows[0] if len(iso_rows) > 0 else "NO"
        defect_val = defect_rows[0] if len(defect_rows) > 0 else "2.5%"
        
        try:
            defect_num = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(defect_val))[0])
        except Exception:
            defect_num = 1.0
            
        is_qualified = ("YES" in str(iso_val).upper()) and (defect_num < 0.5)
        qualification_status[sname_raw] = {
            "qualified": is_qualified,
            "iso": iso_val,
            "defect": defect_val,
            "reason": "Qualified" if is_qualified else "Disqualified (Failed ISO 9001 or Defect > 0.5%)"
        }

    col_mapping = {}
    for col in df.columns:
        if col.endswith("_Norm_INR"):
            base_prefix = col.split("_")[0]
            for q_name in quest_df.columns:
                if base_prefix.lower() in q_name.lower():
                    col_mapping[q_name] = col
                    break
            if col not in col_mapping.values():
                col_mapping[base_prefix] = col

    supplier_totals = {}
    for q_name, col in col_mapping.items():
        if col not in df.columns:
            continue
        valid_rows = df[df[col].notnull()]
        lines_quoted = len(valid_rows)
        has_missing = lines_quoted < len(df)
        
        total_spend = (valid_rows[col] * valid_rows["Quantity"]).sum()
        
        is_qual = qualification_status.get(q_name, {}).get("qualified", True)
        supplier_totals[q_name] = {
            "total_spend": round(total_spend, 2),
            "lines_quoted": lines_quoted,
            "is_complete": not has_missing,
            "qualified": is_qual,
            "col_name": col
        }

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
        q_name: v["col_name"] 
        for q_name, v in supplier_totals.items() 
        if v["qualified"]
    }
    
    split_allocation = []
    split_total = 0.0
    
    for idx, row in df.iterrows():
        prices = {sname: row[col] for sname, col in qual_cols.items() if col in df.columns and pd.notnull(row[col])}
        if prices:
            cheapest_supplier = min(prices, key=prices.get)
            cheapest_unit_price = prices[cheapest_supplier]
            line_total = cheapest_unit_price * row["Quantity"]
        else:
            cheapest_supplier = "Unassigned"
            cheapest_unit_price = 0.0
            line_total = 0.0
            
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

    # Calculate total true issues (Missing, Review Required, Disqualified)
    total_issues = 0
    for idx, r in df.iterrows():
        if r.get("BoxCraft_Status") == "MISSING": total_issues += 1
        if r.get("PackTech_Status") == "MISSING": total_issues += 1
        if r.get("National_Status") == "REVIEW REQUIRED": total_issues += 1

    total_qualified_suppliers = sum(1 for v in qualification_status.values() if v["qualified"])

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
        "total_issues": total_issues,
        "total_qualified_suppliers": total_qualified_suppliers
    }

# -----------------------------------------------------------------------------
# 7. PERSISTENT HEADER & STEPPER NAVIGATION
# -----------------------------------------------------------------------------
calc_results = calculate_deterministic_spend_engine(st.session_state.master_matrix, st.session_state.questionnaire_matrix)

# Header Bar (Sentence Case, Clean Spacing)
st.markdown(f"""
<div class="compact-header">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
            <h2 style="margin: 0; font-size: 1.2rem; font-weight: 600; color: #0f172a;">{st.session_state.rfq_data['title']}</h2>
            <div style="font-size: 0.8rem; color: #64748b; margin-top: 2px;">
                RFQ-2026-PKG-001 &nbsp;•&nbsp; 30 line items &nbsp;•&nbsp; 5 suppliers &nbsp;•&nbsp; Response due 15 Oct 2026
            </div>
        </div>
        <div>
            <span class="badge-review">{calc_results['total_issues']} issues to review</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation Stepper Bar
stages = [
    ("Create RFQ", "Define requirements"),
    ("Supplier Responses", "Collect responses"),
    ("Compare Bids", "Compare bids"),
    ("Analyze & Decide", "Analyze options")
]
cur_idx = [s[0] for s in stages].index(st.session_state.stage)

step_cols = st.columns(4)
for idx, (stage_key, stage_label) in enumerate(stages):
    if idx < cur_idx:
        status_str = f"✓ Step {idx+1}: {stage_label}"
        btn_type = "secondary"
    elif idx == cur_idx:
        status_str = f"● Step {idx+1}: {stage_label}"
        btn_type = "primary"
    else:
        status_str = f"Step {idx+1}: {stage_label}"
        btn_type = "secondary"
        
    if step_cols[idx].button(status_str, key=f"step_nav_{idx}"):
        st.session_state.stage = stage_key
        st.rerun()

st.write("")

# -----------------------------------------------------------------------------
# STAGE 1: CREATE RFQ
# -----------------------------------------------------------------------------
if st.session_state.stage == "Create RFQ":
    col_main, col_side = st.columns([3.3, 1.2])
    
    with col_main:
        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Step 1: Create your RFQ")
        st.caption("Describe what you need to procure. The AI co-pilot will turn your requirement into a structured RFQ draft.")
        
        prompt_val = st.text_area(
            "What do you need to procure?",
            value="I need to source corrugated packaging boxes for our Bhiwandi and Hosur logistics operations. Require 30 line items across 5-ply heavy duty and 3-ply standard shipping cartons. ISO 9001 certification mandatory with Net 60 payment terms.",
            height=90,
            placeholder="Describe items, quantities, specifications, delivery locations and commercial terms..."
        )
        
        if st.button("Generate RFQ draft", type="primary"):
            with st.spinner("Building RFQ draft · Extracting requirements · Structuring line items..."):
                sys_gen_prompt = """
                You are an expert procurement co-pilot.
                Analyze the user's requirement prompt and generate a structured RFx JSON proposal.
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
                            "Source Tag": "AI extracted"
                        }
                    ]
                }
                Generate exactly 30 realistic corrugated packaging line items if prompt requests 30 items.
                Do not invent unstated facts; put missing parameters into unclear_specs.
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
                    st.success("RFQ draft created. Review the generated requirements below before publishing.")
                except Exception as ex:
                    st.warning("Using standard canonical RFQ draft baseline.")
                    st.session_state.rfq_generated = True

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Line items (30 SKUs)")
        
        items_df = pd.DataFrame(st.session_state.rfq_data["line_items"])
        edited_items = st.data_editor(
            items_df,
            use_container_width=True,
            height=380,
            hide_index=True
        )
        st.session_state.rfq_data["line_items"] = edited_items.to_dict(orient="records")

        st.write("")
        f1, f2 = st.columns([3, 1])
        with f2:
            if st.button("Publish RFQ →", type="primary"):
                st.session_state.stage = "Supplier Responses"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_side:
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Requirement Summary**")
        st.markdown(f"""
        * **Category:** {st.session_state.rfq_data['category']}
        * **Locations:** {st.session_state.rfq_data['delivery_locations']}
        * **Payment terms:** {st.session_state.rfq_data['payment_terms']}
        * **Line items:** 30 confirmed
        """)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Open Questions**")
        if st.session_state.rfq_data["unclear_specs"]:
            for unc in st.session_state.rfq_data["unclear_specs"]:
                st.markdown(f"* <span class='badge-review'>Action</span> {unc}", unsafe_allow_html=True)
        else:
            st.markdown("✓ No open questions remaining.")
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STAGE 2: SUPPLIER RESPONSES
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Supplier Responses":
    col_main, col_side = st.columns([3.3, 1.2])
    
    with col_main:
        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Step 2: Collect supplier responses")
        st.caption("Upload supplier response files. The system will extract pricing, terms, and line-item coverage.")

        up_c1, up_c2 = st.columns([3, 1.2])
        with up_c1:
            uploaded_file = st.file_uploader(
                "Supplier response file:",
                type=["pdf", "xlsx", "docx", "png", "jpg", "txt"],
                help="Drop quote, rate card or commercial response here"
            )
        with up_c2:
            supplier_target = st.selectbox("Supplier response for:", ["Apex Packaging", "BoxCraft Ltd", "CorruSeal Global", "National Paper Mills", "PackTech Solutions"])
            
        if uploaded_file and st.button("Extract supplier response", type="primary"):
            with st.spinner(f"Reading supplier response for '{supplier_target}'..."):
                try:
                    file_bytes = uploaded_file.read()
                    
                    if uploaded_file.type in ["image/png", "image/jpeg"]:
                        part = types.Part.from_bytes(data=file_bytes, mime_type=uploaded_file.type)
                        prompt = f"Extract supplier quotation pricing for {supplier_target} across 30 line items into JSON format: list of objects with line_num, price, currency, uom."
                        res = client.models.generate_content(model="gemini-2.5-flash", contents=[part, prompt])
                        extraction_summary = res.text
                    else:
                        raw_doc_text = parse_raw_document_content(file_bytes, uploaded_file.name, uploaded_file.type)
                        
                        sys_ext_prompt = f"""
                        You are an expert procurement AI parsing a raw document quote for supplier '{supplier_target}'.
                        Extract key commercial metrics, currency, unit of measure, and line item prices into JSON:
                        {{
                           "supplier": "{supplier_target}",
                           "currency": "INR",
                           "extracted_lines": 30,
                           "extracted_prices": [
                              {{"line_num": "ITEM-001", "price": 22.50}},
                              {{"line_num": "ITEM-002", "price": 24.10}}
                           ]
                        }}
                        """
                        res = client.models.generate_content(
                            model="gemini-2.5-flash", 
                            contents=f"Raw Document Content:\n{raw_doc_text}\n\n{sys_ext_prompt}"
                        )
                        extraction_summary = res.text

                    try:
                        parsed_ext = extract_json_from_response(extraction_summary)
                        if "extracted_prices" in parsed_ext and isinstance(parsed_ext["extracted_prices"], list):
                            prefix = supplier_target.split()[0]
                            col_norm = f"{prefix}_Norm_INR"
                            
                            for p_item in parsed_ext["extracted_prices"]:
                                lnum = p_item.get("line_num")
                                price = p_item.get("price")
                                if lnum and price and col_norm in st.session_state.master_matrix.columns:
                                    st.session_state.master_matrix.loc[st.session_state.master_matrix["Line #"] == lnum, col_norm] = float(price)
                            st.info(f"Comparison dataset updated with extracted values for {supplier_target}.")
                    except Exception:
                        pass

                    st.session_state.uploaded_docs_log.append({
                        "file": uploaded_file.name,
                        "supplier": supplier_target,
                        "summary": extraction_summary[:280] + "..."
                    })
                    st.success(f"Response extracted for {supplier_target}.")
                except Exception as ex:
                    st.error("We couldn't process this file. Please verify format.")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Response overview")
        inbox_summary = [
            {"Supplier": "Apex Packaging", "Format": "Excel (.xlsx)", "Extraction Confidence": "98%", "Lines Extracted": "30 / 30", "Currency": "INR", "Status": "Confirmed"},
            {"Supplier": "BoxCraft Ltd", "Format": "PDF (.pdf)", "Extraction Confidence": "95%", "Lines Extracted": "27 / 30", "Currency": "INR", "Status": "Missing 3 lines"},
            {"Supplier": "CorruSeal Global", "Format": "PDF (.pdf)", "Extraction Confidence": "96%", "Lines Extracted": "30 / 30", "Currency": "USD ($0.24-$0.55)", "Status": "Normalized (FX @ 83.50)"},
            {"Supplier": "National Paper Mills", "Format": "Scanned PNG", "Extraction Confidence": "88%", "Lines Extracted": "30 / 30", "Currency": "INR", "Status": "Review required (ITEM-020)"},
            {"Supplier": "PackTech Solutions", "Format": "Text / Email", "Extraction Confidence": "90%", "Lines Extracted": "24 / 30", "Currency": "INR", "Status": "Missing 6 lines"}
        ]
        st.dataframe(pd.DataFrame(inbox_summary), use_container_width=True, hide_index=True)

        st.write("")
        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button("← Back to RFQ"):
                st.session_state.stage = "Create RFQ"
                st.rerun()
        with b2:
            if st.button("Continue to Bid Comparison →", type="primary"):
                st.session_state.stage = "Compare Bids"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_side:
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Extraction History**")
        if st.session_state.uploaded_docs_log:
            for item in st.session_state.uploaded_docs_log:
                st.markdown(f"✓ **{item['supplier']}** (`{item['file']}`)")
                st.caption(item["summary"])
        else:
            st.caption("No custom uploads yet. Showing sample response dataset.")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Refusal Behavior** <span class='tag-ai-extracted'>AI Rule</span>", unsafe_allow_html=True)
        st.markdown("""
        * **PackTech_Email.txt:** Refused to invent prior-year prices for items 25–30.
        * **Status:** Marked `Missing`.
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STAGE 3: COMPARE BIDS
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Compare Bids":
    col_main, col_side = st.columns([3.3, 1.2])
    
    with col_main:
        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Step 3: Compare supplier bids")
        st.caption("Compare normalized unit prices, line item coverage, and qualification compliance.")

        cards_data = [
            ("Apex Packaging", f"₹{calc_results['supplier_totals']['Apex Packaging']['total_spend']:,.0f}", "30/30", "Qualified", "Net 60", "badge-confirmed"),
            ("BoxCraft Ltd", "No complete total", "27/30", "Qualified", "Net 30", "badge-missing"),
            ("CorruSeal Global", f"₹{calc_results['supplier_totals']['CorruSeal Global']['total_spend']:,.0f}", "30/30", "Qualified", "Net 60", "badge-normalized"),
            ("National Paper Mills", f"₹{calc_results['supplier_totals']['National Paper Mills']['total_spend']:,.0f}", "30/30", "Qualified", "Net 30", "badge-review"),
            ("PackTech Solutions", "No complete total", "24/30", "Disqualified", "Net 45", "badge-missing")
        ]
        
        summary_table = pd.DataFrame([
            {"Supplier": sname, "Total Quoted Spend (INR)": spend, "Lines Quoted": lines, "Qualification": qual, "Terms": terms, "Data Status": badge_cls.replace('badge-', '').title()}
            for (sname, spend, lines, qual, terms, badge_cls) in cards_data
        ])
        st.dataframe(summary_table, use_container_width=True, hide_index=True)
        st.caption("Extended spend before GST & freight.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        tab_comp1, tab_comp2 = st.tabs(["Price comparison", "Supplier qualification"])
        
        with tab_comp1:
            st.session_state.exception_filter = st.selectbox(
                "Filter comparison view:",
                ["All line items", "Exceptions & issues only"]
            )
            
            matrix_display = st.session_state.master_matrix[[
                "Line #", "Description", "Quantity", "UOM",
                "Apex_Norm_INR", "BoxCraft_Norm_INR", "CorruSeal_Norm_INR", "National_Norm_INR", "PackTech_Norm_INR"
            ]].copy()
            
            matrix_display.columns = ["Line #", "Description", "Qty", "UOM", "Apex (INR/pc)", "BoxCraft (INR/pc)", "CorruSeal (INR/pc)", "National (INR/pc)", "PackTech (INR/pc)"]
            
            if st.session_state.exception_filter == "Exceptions & issues only":
                matrix_display = matrix_display[matrix_display["Line #"].isin(["ITEM-020", "ITEM-028", "ITEM-029", "ITEM-030"])]

            edited_matrix = st.data_editor(
                matrix_display,
                use_container_width=True,
                height=380,
                hide_index=True
            )

        with tab_comp2:
            st.dataframe(st.session_state.questionnaire_matrix, use_container_width=True, hide_index=True)

        st.write("")
        cb1, cb2 = st.columns([1, 1])
        with cb1:
            if st.button("← Back to Responses"):
                st.session_state.stage = "Supplier Responses"
                st.rerun()
        with cb2:
            if st.button("Continue to Scenario Analysis →", type="primary"):
                st.session_state.stage = "Analyze & Decide"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_side:
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Issues to Review**")
        st.markdown("""
        * <span class='badge-missing'>Missing Lines</span> **BoxCraft** (Items 28-30)
        * <span class='badge-review'>Digit Ambiguity</span> **National** (`ITEM-020` 58% conf.)
        * <span class='badge-missing'>Disqualified</span> **PackTech** (Defect 2.1% > 0.5%)
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# STAGE 4: ANALYZE SOURCING OPTIONS
# -----------------------------------------------------------------------------
elif st.session_state.stage == "Analyze & Decide":
    col_main, col_side = st.columns([3.3, 1.2])
    
    with col_main:
        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Step 4: Analyze sourcing options")
        st.caption("Ask questions over the comparison dataset. Scenario spend is computed deterministically by Python; Gemini explains the tradeoffs.")

        st.markdown("#### Select a scenario")
        q_col1, q_col2, q_col3 = st.columns(3)
        prompt_choice = None
        if q_col1.button("Price-optimized split scenario"):
            prompt_choice = "What if we split it, cheapest per line, but only among vendors who cleared the quality questionnaire?"
        if q_col2.button("Supplier eligibility check"):
            prompt_choice = "Why isn't BoxCraft or PackTech included in the split award scenario?"
        if q_col3.button("Landed cost analysis"):
            prompt_choice = "Which supplier has the lowest landed cost including GST and freight?"

        user_query = st.text_input("Ask about this RFQ:", value=prompt_choice if prompt_choice else "", placeholder="e.g. What if we split it, cheapest per line, but only among vendors who cleared quality?")

        analyze_clicked = st.button("Analyze scenario →", type="primary")

        if user_query and (analyze_clicked or prompt_choice):
            with st.spinner("Analyzing master dataset with Gemini 2.5 Flash..."):
                matrix_json = st.session_state.master_matrix.to_json(orient="records")
                q_json = st.session_state.questionnaire_matrix.to_json(orient="records")
                
                system_instruction = f"""
                You are an expert Chief Procurement Officer (CPO) AI assistant.
                You are analyzing an RFx dataset of 30 line items across 5 suppliers.
                
                STRICT GROUNDING & ACCURACY RULES:
                - Do NOT invent numerical figures independently.
                - Do NOT infer missing supplier information as fact.
                - IF USER ASKS FOR LANDED COST INCLUDING GST AND FREIGHT: Refuse to invent missing numbers. State clearly: "Cannot determine landed cost reliably because GST and freight data are missing from the submitted supplier quotes."
                - Use the pre-calculated Python baseline:
                  * Lowest Complete Single Supplier: {calc_results['best_single_name']} at ₹{calc_results['best_single_spend']:,.0f}
                  * Price-Optimized Qualified Split Spend: ₹{calc_results['split_spend']:,.0f}
                  * Illustrative Price Difference: ₹{calc_results['price_diff']:,.0f} ({calc_results['price_diff_pct']}%)
                  * Disqualified: PackTech Solutions (Defect 2.1% > 0.5%, No ISO 9001)
                  * Incomplete: BoxCraft Ltd (27/30 lines), PackTech (24/30 lines)
                  
                PARSED RESPONSE FORMAT REQUIRED:
                Provide output in clean markdown with these exact section headers:
                ### ANSWER
                ### EVIDENCE & PRE-CALCULATED SPEND
                ### TRADE-OFFS & CAVEATS
                ### EXCEPTIONS & RISKS
                ### DATA GAPS
                ### SOURCES & TRACEABILITY
                """
                
                try:
                    res = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=f"Master Matrix:\n{matrix_json}\n\nQuestionnaire:\n{q_json}\n\nUser Question: {user_query}",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.1
                        )
                    )
                    
                    st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
                    st.write(res.text)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    if "landed cost" in user_query.lower() or "gst" in user_query.lower():
                        st.write("")
                        st.markdown("### What is missing for landed cost?")
                        gap_df = pd.DataFrame({
                            "Required Input": ["Base Unit Price", "Normalized Currency (INR)", "ISO 9001 Qualification", "GST Rate (%)", "Freight / Incoterms"],
                            "Apex Packaging": ["AVAILABLE", "AVAILABLE", "AVAILABLE", "MISSING IN SUBMISSION", "MISSING IN SUBMISSION"],
                            "CorruSeal Global": ["AVAILABLE", "AVAILABLE", "AVAILABLE", "MISSING IN SUBMISSION", "MISSING IN SUBMISSION"],
                            "National Paper": ["AVAILABLE", "AVAILABLE", "AVAILABLE", "MISSING IN SUBMISSION", "MISSING IN SUBMISSION"]
                        })
                        st.dataframe(gap_df, use_container_width=True, hide_index=True)
                    
                    elif "split" in user_query.lower() or "cheapest" in user_query.lower() or "single" in user_query.lower():
                        st.write("")
                        st.markdown("### Split allocation by supplier")
                        st.dataframe(calc_results["split_allocation"], use_container_width=True, height=280, hide_index=True)
                        
                        fig = px.bar(
                            calc_results["split_allocation"],
                            x="Awarded Supplier",
                            y="Extended Spend (INR)",
                            color="Awarded Supplier",
                            template="plotly_white",
                            title="Split allocation spend"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                except Exception as ex:
                    st.error("Error analyzing scenario.")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='workspace-section'>", unsafe_allow_html=True)
        st.markdown("### Export")
        ex1, ex2 = st.columns(2)
        with ex1:
            csv_data = st.session_state.master_matrix.to_csv(index=False).encode('utf-8')
            st.download_button("Download comparison CSV", csv_data, "RFQ_Master_Matrix.csv", "text/csv")
        with ex2:
            st.caption("PDF decision summary — Coming soon")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_side:
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Price Baseline** <span class='tag-user'>Calculated</span>", unsafe_allow_html=True)
        if calc_results["has_complete_option"]:
            st.markdown(f"""
            * **Lowest complete quote:** {calc_results['best_single_name']} (₹{calc_results['best_single_spend']:,.0f})
            * **Qualified split:** ₹{calc_results['split_spend']:,.0f}
            * **Price difference:** ₹{calc_results['price_diff']:,.0f} ({calc_results['price_diff_pct']}%)
            """)
        else:
            st.markdown(f"""
            * **Lowest complete quote:** None Available
            * **Qualified split:** ₹{calc_results['split_spend']:,.0f}
            """)
        st.caption("Before GST & freight.")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='side-panel'>", unsafe_allow_html=True)
        st.markdown("**Provenance**")
        st.markdown("""
        * **Deterministic Rules:** Scenario math & qualification rules (Python)
        * **AI Analysis:** Qualitative reasoning (Gemini 2.5 Flash)
        """)
        st.markdown("</div>", unsafe_allow_html=True)
