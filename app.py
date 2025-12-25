import streamlit as st
import google.generativeai as genai
import PyPDF2
import pandas as pd
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date

# --- CONFIGURATION ---
st.image("nama-logo.png")
st.set_page_config(page_title="NAMA Compliance Agent", layout="wide", page_icon="nama-logo.png")
# --- HIDE STREAMLIT STYLE ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ... rest of your code ...
# --- 1. API KEY SETUP ---
# Replace with st.secrets["GEMINI_API_KEY"] in production
api_key =  st.secrets["auth_key"] 
# --- CONSTANTS ---
REQUIRED_DOCS = [
    "Fees application receipt copy",
    "Nama Water Services vendor registration certificates & product agency certificates or authorization letter from the factory for the local distributor, ratified by the Oman Embassy",
    "Certificate of incorporation of the firm (Factory & Foundry)",
    "Manufacturing process flow chart of the product and list of outsourced processes/operations (if applicable), including outsourcing company name & address",
    "Valid copies of certificates (ISO 9001, ISO 45001 & ISO 14001)",
    "Factory layout chart",
    "Factory organizational structure, hierarchy levels, and ownership details",
    "Product compliance statement with reference to Nama Water Services specifications (with supporting documents)",
    "Product technical datasheets",
    "Omanisation details from the Ministry of Labour",
    "Product independent test certificates",
    "Attestation of sanitary conformity (hygiene test including mechanical assessment for a full product certificate at 50°C for use in drinking water)",
    "Product chemical composition of materials",
    "Reference list of products used in Oman or other GCC projects, including contact numbers or email addresses of end users or clients"
]

# --- HELPER FUNCTIONS ---

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text[:25000]
    except Exception as e:
        return f"Error reading file: {e}"

def clean_json_string(json_str):
    cleaned = re.sub(r"```json\s*", "", json_str)
    cleaned = re.sub(r"```", "", cleaned)
    return cleaned.strip()

# --- ONLINE WRAS CHECKER ---
def verify_wras_online(wras_id):
    if not wras_id or wras_id == "N/A":
        return {"status": "Skipped", "details": "No ID extracted"}

    search_url = f"https://www.wrasapprovals.co.uk/approvals-directory/?search={wras_id}"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {"status": "Connection Error", "details": f"HTTP {response.status_code}"}

        if "No results found" in response.text:
             return {
                "status": "Not Found",
                "url": search_url
            }
        
        return {
            "status": "Active / Found",
            "online_id": wras_id, 
            "url": search_url
        }

    except Exception as e:
        return {"status": "Scraping Error", "details": str(e)}

# --- CORE AI ANALYSIS ---
def analyze_documents(files_data, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-3-pro-preview') 
        today_str = date.today().strftime("%Y-%m-%d")

        system_prompt = f"""
        You are an expert NAMA Compliance Auditor. Today is **{today_str}**.
        MANDATORY LIST: {json.dumps(REQUIRED_DOCS)}

        **TASK 1: ISO CERTIFICATES (Strict 180-day Rule)**
        - Extract Cert #, Expiry, Address.
        - FAIL if days_remaining < 180.
        
        **TASK 2: WRAS CERTIFICATE**
        - Look for "Attestation of Sanitary Conformity" or "WRAS".
        - EXTRACT: WRAS Approval Number (ID), Product, Manufacturer.
        
        **TASK 3: GENERAL & MISSING DOCS**
        - Identify which files match the MANDATORY LIST.
        - Identify which documents from the MANDATORY LIST are **MISSING**.

        Output Format (Strict JSON):
        {{
            "iso_analysis": [
                {{
                    "standard": "ISO 9001",
                    "expiry_date": "YYYY-MM-DD",
                    "days_remaining": 0,
                    "compliance_status": "Pass/Fail",
                    "confidence_score": 0.9
                }}
            ],
            "wras_analysis": {{
                "found": true,
                "wras_id": "123456",
                "manufacturer_pdf": "...",
                "product_pdf": "..."
            }},
            "found_documents": [
                {{ "filename": "...", "Type": "...", "Status": "Valid" }}
            ],
            "missing_documents": [
                "Name of missing document 1",
                "Name of missing document 2"
            ],
            "overall_score": 0
        }}
        """

        user_message = "Here are the uploaded documents:\n"
        for file in files_data:
            user_message += f"\n--- FILE: {file['name']} ---\n{file['content']}\n"

        response = model.generate_content(
            contents=[system_prompt, user_message],
            generation_config={"response_mime_type": "application/json"}
        )
        
        ai_result = json.loads(clean_json_string(response.text))
        
        # Trigger Python WRAS Scraper if ID found
        if ai_result.get("wras_analysis", {}).get("found"):
            wras_id = ai_result["wras_analysis"].get("wras_id")
            ai_result["wras_analysis"]["online_verification"] = verify_wras_online(wras_id)
            
        return ai_result

    except Exception as e:
        return {"error": f"AI Processing Error: {str(e)}"}

# --- UI LOGIC ---

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

#with st.sidebar:
st.header("Upload Center")
uploaded_files = st.file_uploader("Select PDFs", type=["pdf"], accept_multiple_files=True)
if st.button("Run Full Compliance Audit", type="primary"):
    if uploaded_files:
        with st.spinner("🕵️ Analyzing Docs, Checking WRAS, Validating ISO..."):
            content = []
            for f in uploaded_files:
                content.append({"name": f.name, "content": extract_text_from_pdf(f)})
                st.session_state.analysis_result = analyze_documents(content, api_key)

# DASHBOARD
if st.session_state.analysis_result:
    res = st.session_state.analysis_result
    
    if "error" in res:
        st.error(res['error'])
    else:
        st.title("🛡️ Compliance Audit Report")
        
        # 1. METRICS
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Score", f"{res.get('overall_score', 0)}/100")
        col2.metric("Missing Docs", len(res.get('missing_documents', [])))
        
        wras_status = res.get("wras_analysis", {}).get("online_verification", {}).get("status", "Not Checked")
        col3.metric("WRAS Status", wras_status)
        col4.metric("ISO Certs", len(res.get('iso_analysis', [])))
        
        st.divider()

        # 2. MISSING DOCUMENTS ALERT (RESTORED)
        missing = res.get('missing_documents', [])
        if missing:
            st.error(f"⚠️ **Compliance Gaps: {len(missing)} Missing Documents**")
            
            # Display as a clean list/table
            for m in missing:
                st.markdown(f"- ❌ **{m}**")
        else:
            st.success("✅ **Perfect! All mandatory documents are present.**")

        st.divider()

        # 3. WRAS DEEP DIVE
        st.subheader("💧 WRAS Verification (Doc #12)")
        wras_data = res.get("wras_analysis", {})
        
        if wras_data.get("found"):
            w1, w2 = st.columns(2)
            with w1:
                st.info(f"**PDF Extraction:**\n- ID: {wras_data.get('wras_id')}\n- Mfg: {wras_data.get('manufacturer_pdf')}")
            with w2:
                online = wras_data.get("online_verification", {})
                if online.get("status") == "Active":
                    st.success(f"✅ Active on Database\n[Link]({online.get('url')})")
                elif online.get("status") == "Not Found":
                    st.error(f"❌ ID Not Found Online")
                else:
                    st.warning(f"⚠️ {online.get('status')}")
        else:
            st.write("No WRAS certificate found.")

        st.divider()

        # 4. ISO VALIDATION
        st.subheader("🏭 ISO Validation (180-Day Rule)")
        iso_data = res.get('iso_analysis', [])
        if iso_data:
            cols = st.columns(len(iso_data)) if len(iso_data) > 0 else [st.container()]
            for idx, iso in enumerate(iso_data):
                with cols[idx % 3]:
                    status_color = "green" if "Pass" in iso['compliance_status'] else "red"
                    with st.container(border=True):
                        st.markdown(f"#### :{status_color}[{iso['standard']}]")
                        days = iso['days_remaining']
                        if days < 180:
                            st.error(f"⚠️ {days} days left (<180)")
                        else:
                            st.success(f"✅ {days} days left")
                        st.caption(f"Expires: {iso.get('expiry_date')}")

        # 5. FOUND DOCUMENTS TABLE
        with st.expander("📂 View Submitted Documents List"):

             st.dataframe(pd.DataFrame(res.get('found_documents', [])))





