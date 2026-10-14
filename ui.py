from __future__ import annotations
import base64
import datetime as dt
import hashlib
import html
import io
import json
import logging
import os
from pathlib import Path
import uuid
import pandas as pd
import streamlit as st
import core
import engine
import storage

ROOT=Path(__file__).parent
FORMATS=['pdf','xlsx','docx','png','jpg','jpeg','txt','csv','eml']
LABELS={
    'id':'Reference','description':'Item','specification':'Specifications / dimensions','quantity':'Quantity','uom':'Unit',
    'location':'Delivery location','max_lead_days':'Maximum lead time (days)','label':'Supplier question','mandatory':'Required',
    'rule':'Pass rule','threshold':'Limit','unit':'Unit','name':'Term','value':'Answer / details','origin':'Source of requirement',
    'line_id':'Requested item','vendor_description':'Supplier item / specifications','price':'Quoted price','currency':'Currency',
    'quoted_uom':'Quoted unit','price_basis':'Price per how many units?','file':'Source file','locator':'Page / row / line',
    'excerpt':'Supporting source text','uncertainty':'Unresolved issue','issue_resolution':'How you resolved the issue',
    'discount_pct':'Discount (%)','discount_evidence':'Discount evidence','discount_conditional':'Conditional discount',
    'unconditional_base_price':'Unconditional base price (quoted currency)','conditional_min_quantity':'Discount minimum line quantity',
    'target_units_per_quoted_unit':'Requested units per quoted unit','conversion_evidence':'Conversion evidence',
    'specification_checked':'Item match and specifications checked','valid_until':'Quote valid until (YYYY-MM-DD)',
    'capacity':'Available quantity (requested units)','min_order':'Minimum order (requested units)',
    'order_multiple':'Order multiple (requested units)','lead_days':'Lead time (days)','constraints_checked':'Quoted constraints checked',
    'tax_pct':'Tax (%)','duty_pct':'Duty (%)','freight_inr':'Line freight (INR)','costs_checked':'Line costs checked, including zero amounts',
    'excluded':'Exclude alternative','approved':'Confirm this version','question_id':'Question reference',
    'numeric_value':'Numeric answer','certificate_state':'Certificate state','expiry':'Certificate expiry (YYYY-MM-DD)',
}

def columns():
    result={key:st.column_config.Column(label) for key,label in LABELS.items()}
    for key in ['quantity','price','price_basis','capacity','min_order','order_multiple']:
        result[key]=st.column_config.NumberColumn(LABELS[key],min_value=0.000001,format='%.6f')
    result['rule']=st.column_config.SelectboxColumn('Pass rule',options=['information','valid_certificate','yes','max','min'])
    result['certificate_state']=st.column_config.SelectboxColumn('Certificate state',options=['VALID','EXPIRED','CLAIMED','MISSING','NO','NOT APPLICABLE'])
    result['origin']=st.column_config.SelectboxColumn('Source of requirement',options=['USER PROVIDED','AI SUGGESTED','BUYER CONFIRMED'])
    for key in ['approved','mandatory','specification_checked','costs_checked','constraints_checked','excluded','discount_conditional']:
        result[key]=st.column_config.CheckboxColumn(LABELS[key])
    return result

def styles():
    st.markdown('''<style>
    .stApp {background:#f3f6f8}
    .block-container {max-width:1440px;padding-top:2.2rem;padding-bottom:4rem}
    h1,h2,h3 {letter-spacing:-.035em;color:#162a3a}
    h1 {font-size:2.3rem!important} h2 {font-size:1.45rem!important}
    [data-testid="stSidebar"]{background:#fff;border-right:1px solid #e2e9ed}
    [data-testid="stSidebar"] .block-container {padding-top:2rem}
    [data-testid="stMetric"] {background:white;border:1px solid #e2e9ed;border-radius:16px;padding:18px 22px}
    [data-testid="stMetricValue"] {font-size:1.9rem;font-weight:700}
    [data-testid="stForm"] {background:#fff;border-radius:18px;border:1px solid #e2e9ed;padding:24px}
    .stButton>button,.stDownloadButton>button {border-radius:10px;min-height:42px;font-weight:600}
    .hero {background:linear-gradient(115deg,#142d3c,#173e4e);padding:30px 34px;border-radius:22px;color:#fff;margin:0 0 24px}
    .hero .eyebrow {color:#8cddd0;font-size:.72rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase}
    .hero h1 {color:#fff;font-size:2.3rem!important;margin:10px 0 8px;line-height:1.15}
    .hero p {color:#c3d7df;max-width:760px;font-size:.98rem;margin:0;line-height:1.7}
    .brand {display:flex;align-items:center;gap:12px;margin:0 0 28px;font-size:1.22rem;font-weight:750;color:#173342}
    .brand-icon {background:#087f6d;color:#fff;border-radius:11px;width:36px;height:36px;display:grid;place-items:center}
    .kicker {color:#64818e;font-size:.72rem;letter-spacing:.13em;text-transform:uppercase;font-weight:700}
    .aside-note {background:#eef8f5;border:1px solid #d0e9e1;border-radius:12px;padding:15px;color:#254f46;font-size:.88rem;line-height:1.6;margin-top:20px}
    .supplier-card {background:white;border:1px solid #e0e8ed;border-radius:16px;padding:20px;margin:12px 0}
    .supplier-card .state {font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;font-weight:750}
    .supplier-card h3 {font-size:1.12rem;margin:10px 0}
    .supplier-card p {font-size:.88rem;color:#526b79;line-height:1.5;margin:0}
    .supplier-card.ready {border-top:4px solid #087f6d}.supplier-card.check {border-top:4px solid #d39431}.supplier-card.rejected {border-top:4px solid #bf5151}
    .supplier-card.awaiting {border-top:4px solid #94a8b3}
    .table-wrap {overflow:auto;border:1px solid #dce6ea;border-radius:14px;background:white;margin:14px 0;max-height:480px}
    .table-wrap table {width:100%;border-collapse:collapse;font-size:.85rem}
    .table-wrap th {position:sticky;top:0;background:#edf3f5;padding:14px;text-align:left;white-space:nowrap;color:#496371;z-index:1}
    .table-wrap td {padding:13px 14px;border-bottom:1px solid #edf2f5;min-width:120px}
    .table-wrap td.best {background:#e8f7ef;color:#126348;font-weight:700}
    .step-note {color:#627c88;font-size:.9rem;margin:4px 0 18px}
    .empty-panel {background:white;border:1px dashed #bdd0d8;border-radius:18px;padding:40px;text-align:center;margin:20px 0}
    .empty-panel h3 {margin:8px 0}.empty-panel p {color:#627c88;font-size:.92rem}
    [data-testid="stAlert"]{border-radius:12px}
    @media(max-width:700px){.block-container{padding:1rem}.hero{padding:24px}.hero h1{font-size:1.8rem!important}}
    </style>''',unsafe_allow_html=True)

def secret(key,default=None):
    try: return st.secrets.get(key,os.environ.get(key,default))
    except Exception: return os.environ.get(key,default)

def identity():
    required=str(secret('QUOTECOMPARE_AUTH_REQUIRED','false')).lower()=='true'
    if not required: return 'local-private','Local buyer'
    if not st.user.is_logged_in:
        st.title('Your sourcing workspace')
        st.write('Sign in to access your private requests and supplier documents.')
        if st.button('Sign in',type='primary'): st.login()
        st.stop()
    email=str(st.user.get('email','')).lower()
    subject=str(st.user.get('sub',''))
    issuer=str(st.user.get('iss',''))
    allow=secret('QUOTECOMPARE_ALLOWED_USERS',[])
    if isinstance(allow,str): allow=[x.strip().lower() for x in allow.split(',') if x.strip()]
    if not subject or not allow or email not in {x.lower() for x in allow}:
        st.error('This account is not allowed to access QuoteCompare.'); st.stop()
    return hashlib.sha256((issuer+'|'+subject).encode()).hexdigest(),email

def persist(w,action=None,details=None):
    if action: core.record(w,action,{'reviewer':st.session_state.reviewer,'details':details})
    storage.save(st.session_state.db,st.session_state.owner,w)
    st.session_state.saved_at=dt.datetime.now().strftime('%H:%M')

def rerun(w,action=None,details=None):
    persist(w,action,details)
    st.session_state.pop('answer',None)
    st.session_state.pop('suggestions',None)
    st.rerun()

def records(frame,model):
    rows=json.loads(frame.to_json(orient='records',double_precision=15))
    cleaned=[]
    for row in rows:
        clean={}
        for key,value in row.items():
            field=model.model_fields[key]
            if value is None and not field.is_required() and field.default is not None: continue
            clean[key]=value
        cleaned.append(model.model_validate(clean))
    return cleaned

def provenance(updated,previous):
    lookup={getattr(x,'id',x.name if hasattr(x,'name') else ''):x for x in previous}
    for field in updated:
        key=getattr(field,'id',field.name if hasattr(field,'name') else '')
        old=lookup.get(key)
        if old is None:
            field.origin='USER PROVIDED'; field.creation_origin='USER PROVIDED'
        else:
            field.creation_origin=old.creation_origin or old.origin
            exclude={'origin','creation_origin'}
            before={k:v for k,v in core.dump(old).items() if k not in exclude}
            after={k:v for k,v in core.dump(field).items() if k not in exclude}
            if engine.canonical_hash(before)!=engine.canonical_hash(after): field.origin='USER PROVIDED'
    return updated

def encode_files(files):
    return [{'name':f['name'],'data':base64.b64encode(f['data']).decode(),'hash':hashlib.sha256(f['data']).hexdigest()} for f in files]

def ai(action,label):
    if not (secret('GEMINI_API_KEY') or secret('GCP_SERVICE_ACCOUNT')):
        st.info('AI is not configured yet. You can create and review requests manually, or explore the demo.'); return None
    try:
        from google import genai
        from google.genai import types
        account=secret('GCP_SERVICE_ACCOUNT')
        if account:
            from google.oauth2 import service_account
            info=json.loads(account) if isinstance(account,str) else dict(account)
            info.setdefault('token_uri','https://oauth2.googleapis.com/token')
            credentials=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/cloud-platform'])
            client=genai.Client(vertexai=True,project=info['project_id'],location=secret('GCP_LOCATION','us-central1'),credentials=credentials,http_options=types.HttpOptions(timeout=120000))
        else: client=genai.Client(api_key=secret('GEMINI_API_KEY'),http_options=types.HttpOptions(timeout=120000))
        with st.spinner(label),client:
            return action(client,secret('GEMINI_MODEL','gemini-2.5-flash'))
    except Exception:
        reference=uuid.uuid4().hex[:8]
        logging.warning('AI request failed reference=%s',reference)  # no documents or credentials in UI/logs
        st.error(f'AI could not finish this request. Your saved work is unchanged. Retry later. Reference: {reference}')
        return None

def source_view(files,key):
    if not files: st.info('No source documents saved.'); return
    names=[f['name'] for f in files]
    old=st.session_state.get(key)
    if old not in names: st.session_state[key]=names[0]
    selected=st.selectbox('Source document',names,key=key)
    f=next(f for f in files if f['name']==selected)
    raw=base64.b64decode(f['data']); ext=Path(selected).suffix.lower()
    st.download_button('Download original',raw,selected,key=key+'_download')
    try:
        if ext=='.pdf':
            import fitz
            with fitz.open(stream=raw,filetype='pdf') as doc:
                pagekey=key+'_'+f['hash']+'_page'
                page=st.number_input('Page',1,len(doc),1,key=pagekey)
                p=doc[page-1]
                scale=min(1.4,1800/max(p.rect.width,p.rect.height))
                st.image(p.get_pixmap(matrix=fitz.Matrix(scale,scale)).tobytes('png'))
        elif ext in {'.png','.jpg','.jpeg'}: st.image(raw)
        else:
            st.code(core.source_text(selected,raw),language=None)
            if ext=='.docx':
                import zipfile
                engine.safe_archive(raw)
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    for member in z.namelist():
                        if member.startswith('word/media/') and member.lower().endswith(('.png','.jpg','.jpeg')): st.image(z.read(member),caption=member)
    except Exception: st.warning('Preview unavailable. Download the source and open it in its original application.')

def sidebar(w):
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-icon">Q</span>QuoteCompare</div>',unsafe_allow_html=True)
        st.markdown('<div class="kicker">RFQ & supplier comparison</div>',unsafe_allow_html=True)
        st.caption('A clearer path from requirement to buying decision.')
        st.divider()
        st.write('**Your workspace**')
        st.caption(w['rfq']['title'] if w['rfq'] else 'New request')
        st.caption(f"{len(w['suppliers'])} suppliers · {len(w['responses'])} quotes saved")
        st.caption('Autosaved locally'+(' · '+st.session_state.saved_at if st.session_state.get('saved_at') else ''))
        if w.get('pending_review'): st.warning('Quote review saved as a draft.')
        with st.expander('Workspaces & backups'):
            saved=storage.list_workspaces(st.session_state.db,st.session_state.owner)
            if saved:
                chosen=st.selectbox('Saved request',saved,format_func=lambda x:x[0][:8]+' · '+x[1][:10])
                if st.button('Open saved request'):
                    st.session_state.work=storage.load(st.session_state.db,st.session_state.owner,chosen[0]); st.session_state.step='Create request'; st.rerun()
            st.download_button('Download complete backup',core.workspace_bytes(w),'quotecompare_workspace.json','application/json')
            st.caption('Contains original supplier documents. Store privately. Restored confirmations must be checked again.')
            backup=st.file_uploader('Restore backup',type=['json'])
            if st.button('Restore as a separate workspace',disabled=not backup):
                try:
                    restored=core.load_workspace(backup.getvalue()); restored['workspace_id']=uuid.uuid4().hex
                    st.session_state.work=restored; rerun(restored,'Backup restored; approvals cleared')
                except Exception as exc: st.error('Backup rejected: '+str(exc)[:300])
            if st.button('Start a new request'):
                persist(w); st.session_state.work=core.empty_workspace(); st.session_state.step='Create request'; rerun(st.session_state.work,'Workspace created')
        if not w['rfq'] and st.button('Explore a sample request',width='stretch'):
            st.session_state.work=demo_workspace(); st.session_state.step='Compare quotes'; rerun(st.session_state.work,'Fictional demo loaded')
        st.markdown('<div class="aside-note"><b>Built for checked decisions</b><br>AI drafts and extracts. You verify the source. The app calculates the comparison.</div>',unsafe_allow_html=True)
        st.caption('Private local mode' if st.session_state.owner=='local-private' else 'Signed in as '+st.session_state.reviewer)
        if st.session_state.owner!='local-private' and st.button('Sign out'): st.logout()

def header(w,step):
    titles={'Create request':('Start with a clear requirement.','Build an RFQ your suppliers can quote accurately. Keep specifications, quantities, and required checks together.'),
            'Review quotes':('Turn quotes into checked evidence.','Review item matching, prices, and supplier answers against the originals. Every confirmation belongs to the version you checked.'),
            'Compare quotes':('Make the tradeoffs visible.','Compare qualified suppliers, understand cost and coverage, and save the buying plan you approve.')}
    title,body=titles[step]
    st.markdown('<div class="hero"><div class="eyebrow">QuoteCompare / '+html.escape(step)+'</div><h1>'+title+'</h1><p>'+body+'</p></div>',unsafe_allow_html=True)

def request_screen(w):
    if not w['published']:
        left,right=st.columns([1.65,1],gap='large')
        with left:
            st.subheader('Describe what you need')
            with st.form('brief_form'):
                brief=st.text_area('Requirement brief',height=125,placeholder='100 shipping cartons, 30 × 20 × 15 cm, delivered to Bhiwandi…')
                uploaded=st.file_uploader('Requirement documents',type=FORMATS,accept_multiple_files=True,max_upload_size=18,help='At most 12 files and 36 MB total.')
                st.caption('AI analysis sends this content to your configured Google service. Add only documents you are authorized to share.')
                generate=st.form_submit_button('Draft with AI',type='primary')
            if generate:
                files=[{'name':f.name,'data':f.getvalue()} for f in uploaded]
                if not brief.strip() and not files: st.warning('Describe your requirement or attach a document.')
                else:
                    try:
                        parts=core.prepare_sources(files)[0] if files else []
                        result=ai(lambda client,model:core.ai_json(client,model,core.RFQ,
                            'Draft an RFQ from this brief and documents: '+brief+' Preserve exact provided specifications and quantities. Use stable ITEM-001 and Q-001 references. Missing quantity is null. Mark suggestions AI SUGGESTED. Do not invent obligations. Required rules only when explicitly provided. List unresolved questions.',parts),'Drafting your request…')
                        if result:
                            w['rfq']=core.dump(result); w['request_sources']=encode_files(files); rerun(w,'AI request draft created')
                    except Exception as exc: st.error(str(exc)[:300])
        with right:
            st.subheader('Prefer to start yourself?')
            st.write('Create an editable request with your own items, terms, and supplier checks.')
            if st.button('Create a manual draft',width='stretch'):
                w['rfq']=core.dump(core.RFQ(title='New sourcing request',scope='',items=[core.Item(id='ITEM-001',description='New item',quantity=None,origin='USER PROVIDED')],questions=[],terms=[])); rerun(w,'Manual draft created')
            st.caption('Drafts may be incomplete. Quantities and unresolved questions must be finished before inviting suppliers.')
    if not w['rfq']:
        st.markdown('<div class="empty-panel"><h3>Your next sourcing decision starts here</h3><p>Describe a requirement, create a manual draft, or explore the sample request in the sidebar.</p></div>',unsafe_allow_html=True); return
    rfq=core.RFQ.model_validate(w['rfq'])
    if w['published']:
        st.success(f'Request finished · revision {rfq.revision}. Existing quote scope is locked.')
        with st.expander('Request details'):
            st.text(core.request_text(rfq))
        if st.button('Create a revised request'):
            persist(w)
            new=core.empty_workspace(); clone=rfq.model_copy(deep=True); clone.revision+=1
            new['rfq']=core.dump(clone); new['suppliers']=w['suppliers'].copy(); new['request_sources']=w['request_sources']
            new['rfq_versions']=[{'workspace_id':w['workspace_id'],'rfq':w['rfq']}]
            st.session_state.work=new; rerun(new,'RFQ revision created',{'previous_workspace':w['workspace_id']})
    else:
        st.subheader('Shape your request')
        with st.form('rfq_editor'):
            title=st.text_input('Request title',rfq.title)
            scope=st.text_area('Scope',rfq.scope,height=80)
            st.write('**Items and specifications**')
            item_cols=['id','description','specification','quantity','uom','location','max_lead_days','origin']
            items=st.data_editor(pd.DataFrame([core.dump(i) for i in rfq.items],columns=item_cols),num_rows='dynamic',hide_index=True,column_config=columns(),key='items_'+str(rfq.revision))
            st.caption('Source labels identify suggestions. Buyer confirmation is recorded separately when the request is finished.')
            st.write('**Required supplier checks**')
            qcols=['id','label','mandatory','rule','threshold','unit','origin']
            qs=st.data_editor(pd.DataFrame([core.dump(q) for q in rfq.questions],columns=qcols),num_rows='dynamic',hide_index=True,column_config=columns(),key='questions_'+str(rfq.revision))
            st.write('**Commercial requirements**')
            terms=st.data_editor(pd.DataFrame([core.dump(t) for t in rfq.terms],columns=['name','value','origin']),num_rows='dynamic',hide_index=True,column_config=columns(),key='terms_'+str(rfq.revision))
            resolved=st.multiselect('Requirement questions you have resolved',rfq.open_questions)
            confirm=st.checkbox('I checked the scope, specifications, quantities, required rules and terms.')
            a,b=st.columns(2)
            draft=a.form_submit_button('Save draft',width='stretch')
            finish=b.form_submit_button('Finish request',type='primary',width='stretch')
        if draft or finish:
            try:
                candidate=core.RFQ(title=title,scope=scope,items=provenance(records(items,core.Item),rfq.items),questions=provenance(records(qs,core.Question),rfq.questions),terms=provenance(records(terms,core.Term),rfq.terms),
                    open_questions=[q for q in rfq.open_questions if q not in resolved],resolved_questions=rfq.resolved_questions+resolved,revision=rfq.revision)
                errors=core.validate_rfq(candidate,publish=finish)
                if finish and not confirm: errors.append('Confirm your request before finishing.')
                if errors: st.error(' '.join(errors))
                else: w['rfq']=core.dump(candidate); w['published']=finish; rerun(w,'RFQ finished' if finish else 'Draft saved',{'confirmed':confirm,'revision':rfq.revision})
            except Exception as exc: st.error('Check your request: '+str(exc)[:500])
    if w['request_sources']:
        with st.expander('Original requirement documents'): source_view(w['request_sources'],'requirement_source')
    if w['published']:
        st.subheader('Supplier invitations')
        st.caption('Prepare and download invitations. Email delivery is not connected.')
        with st.form('suppliers_form'):
            names_text=st.text_area('Supplier names · one per line','\n'.join(w['suppliers']),height=110)
            save=st.form_submit_button('Save supplier list')
        if save:
            names=[n.strip() for n in names_text.splitlines() if n.strip()]
            if not 1<=len(names)<=8 or len({n.casefold() for n in names})!=len(names): st.error('Use 1–8 unique supplier names.')
            elif set(w['responses'])-set(names): st.error('A supplier with saved quotes cannot be removed. Create a revised request instead.')
            elif w['pending_review'] and w['pending_review']['supplier'] not in names: st.error('Save or cancel the pending quote before removing its supplier.')
            else: w['suppliers']=names; rerun(w,'Supplier list saved',names)
        if w['suppliers']:
            with st.expander('Invitation package',expanded=True):
                st.download_button('RFQ text',core.request_text(rfq),'supplier_request.txt')
                st.download_button('Item list',core.csv_bytes([core.dump(i) for i in rfq.items]),'rfq_items.csv','text/csv')
                st.download_button('Invitation email draft','Subject: Request for quotation — '+rfq.title+'\n\nPlease quote the items and answer the supplier questions.\n\n'+core.request_text(rfq),'supplier_invitation.txt')
            if st.button('Mark invitations prepared & review quotes',type='primary'):
                w['demo_invited_suppliers']=w['suppliers'].copy(); st.session_state.step='Review quotes'; rerun(w,'Invitations prepared',{'emails_sent':False})

def new_pending(w,supplier,files=None,extraction=None):
    files=files or []
    ext=extraction or core.Extraction(detected_supplier=supplier,bids=[],answers=[],commercials=[])
    return {'supplier':supplier,'rfq_hash':core.fingerprint(w['rfq']),'review_id':uuid.uuid4().hex,
        'extraction':core.dump(ext),'files':encode_files(files),'bundle_hash':core.fingerprint({'supplier':supplier,'rfq':w['rfq'],'files':[(f['name'],hashlib.sha256(f['data']).hexdigest()) for f in files]}),
        'terms_checked':False,'policy':{'cost_mode':w['cost_mode'],'fixed_charge_inr':0,'fixed_charge_checked':False},'revision':1}

def quote_screen(w):
    if not w['published'] or not w['suppliers']: st.info('Finish a request and add suppliers before reviewing quotes.'); return
    rfq=core.RFQ.model_validate(w['rfq'])
    pending=w.get('pending_review')
    if not pending:
        left,right=st.columns([1.6,1],gap='large')
        with left:
            st.subheader('Add a supplier response')
            with st.form('quote_upload'):
                supplier=st.selectbox('Supplier',w['suppliers'])
                uploads=st.file_uploader('Quote, email and certificates',type=FORMATS,accept_multiple_files=True,max_upload_size=18,help='At most 12 files and 36 MB total.')
                email=st.text_area('Pasted email (optional)',height=80)
                st.caption('Replacements remain a draft until saved. Earlier quote revisions are retained.')
                a,b=st.columns(2)
                extract=a.form_submit_button('Extract with AI',type='primary',width='stretch')
                manual=b.form_submit_button('Review manually',width='stretch')
            if extract or manual:
                files=[{'name':f.name,'data':f.getvalue()} for f in uploads]
                if email.strip(): files.append({'name':'pasted_email.txt','data':email.encode()})
                try:
                    if not files: raise ValueError('Add a source document or pasted email.')
                    core.prepare_sources(files)
                    result=ai(lambda client,model:core.extract(client,model,rfq,supplier,files),'Reading your supplier documents…') if extract else core.Extraction(detected_supplier=supplier,bids=[],answers=[])
                    if result: w['pending_review']=new_pending(w,supplier,files,result); rerun(w,'Quote review started',supplier)
                except Exception as exc: st.error(str(exc)[:300])
        with right:
            st.subheader('Saved supplier responses')
            for supplier in w['suppliers']:
                response=w['responses'].get(supplier)
                st.write('**'+supplier+'**')
                st.caption('Awaiting a quote' if not response else f"Revision {response.get('revision',1)} · {len(response['extraction']['bids'])} quoted rows")
                if response and st.button('Open review',key='edit_'+supplier,width='stretch'):
                    w['pending_review']=json.loads(json.dumps(response)); w['pending_review']['review_id']=uuid.uuid4().hex; rerun(w,'Saved quote opened for review',supplier)
            if w['quote_versions']:
                with st.expander('Previous quote revisions'):
                    history_supplier=st.selectbox('Historical supplier',list(w['quote_versions']))
                    versions=w['quote_versions'][history_supplier]
                    revision=st.selectbox('Historical revision',range(len(versions)),format_func=lambda idx:'Revision '+str(versions[idx].get('revision',idx+1)))
                    previous=versions[revision]
                    st.caption('Historical evidence only. Current decisions use the latest committed quote.')
                    source_view(previous['files'],'historical_source_'+history_supplier+'_'+str(revision))
                    st.download_button('Download historical extraction',json.dumps(previous['extraction'],indent=2),'historical_extraction.json')
        return
    st.subheader('Review · '+pending['supplier'])
    if pending['supplier'] in w['responses']: st.caption('Your previous saved quote stays active until you commit this replacement.')
    ext=core.Extraction.model_validate(pending['extraction']); rid=pending['review_id']
    if ext.detected_supplier and core.squash(ext.detected_supplier)!=core.squash(pending['supplier']): st.warning('Supplier name mismatch: the source names '+ext.detected_supplier)
    for warning in ext.warnings: st.warning(warning)
    with st.expander('Original supplier documents',expanded=False): source_view(pending['files'],'review_source_'+rid)
    with st.form('review_'+rid):
        st.write('**1. Match and check prices**')
        st.caption('Reassign any item. Add missing rows. Exclude alternative prices rather than deleting their evidence. Currency and quoted units must be explicit.')
        bid_cols=['line_id','vendor_description','price','currency','quoted_uom','price_basis','specification_checked','excluded','approved']
        configs=columns(); configs['line_id']=st.column_config.SelectboxColumn('Requested item',options=[i.id for i in rfq.items],help='Match against the request references shown below.')
        st.caption(' · '.join(i.id+': '+i.description+(' — '+i.specification if i.specification else '') for i in rfq.items))
        base=pd.DataFrame([core.dump(b) for b in ext.bids],columns=list(core.Bid.model_fields))
        # Full editable records ensure a correction can never hide behind conditional columns.
        advanced=['discount_pct','discount_evidence','discount_conditional','unconditional_base_price','conditional_min_quantity','target_units_per_quoted_unit','conversion_evidence','valid_until','capacity','min_order','order_multiple','lead_days','constraints_checked','tax_pct','duty_pct','freight_inr','costs_checked']
        bids=st.data_editor(base,num_rows='dynamic',hide_index=True,column_config=configs,column_order=bid_cols+['file','locator','excerpt','uncertainty','issue_resolution']+advanced,
            disabled=['review_fingerprint','review_note','checked_at','checked_by','confidence'],key='bids_'+rid)
        st.caption('Scroll right to edit source evidence, discounts, conversions, quote validity, order constraints and line costs.')
        with st.expander('Discounts, conversions, validity, capacity and line costs'):
            st.caption('Constraints use requested units. Freight here is per line. Add supplier-wide fixed charges below. Values need source evidence and explicit buyer confirmation.')
        st.write('**2. Verify supplier answers**')
        if rfq.questions: st.caption(' · '.join(q.id+': '+q.label+(' (required)' if q.mandatory else '') for q in rfq.questions))
        answer_base=pd.DataFrame([core.dump(a) for a in ext.answers],columns=list(core.Answer.model_fields))
        configs['question_id']=st.column_config.SelectboxColumn('Question reference',options=[q.id for q in rfq.questions])
        answers=st.data_editor(answer_base,num_rows='dynamic',hide_index=True,column_config=configs,
            column_order=['question_id','value','numeric_value','unit','certificate_state','expiry','file','locator','excerpt','approved'],disabled=['review_fingerprint','review_note','checked_at','checked_by'],key='answers_'+rid)
        st.write('**3. Review commercial terms**')
        terms=st.data_editor(pd.DataFrame([core.dump(t) for t in ext.commercials],columns=list(core.Commercial.model_fields)),num_rows='dynamic',hide_index=True,column_config=configs,key='commercials_'+rid)
        terms_checked=st.checkbox('I checked the commercial terms against their source documents.',value=pending.get('terms_checked',False))
        fixed=st.number_input('Supplier-wide fixed charges (INR)',min_value=0.,value=float(pending.get('policy',{}).get('fixed_charge_inr',0)),help='Charged once if this supplier is selected. Do not duplicate per-line freight here.')
        fixed_checked=st.checkbox('I confirmed the fixed charge, including an explicit zero.',value=pending.get('policy',{}).get('fixed_charge_checked',False))
        st.divider()
        all_checked=st.checkbox('Confirm all clear prices and listed answers for this version against the original documents.')
        st.caption('Unresolved issues, duplicate active prices and missing evidence are skipped. Changed approved values require a fresh confirmation.')
        note=st.text_input('Review comment (optional)')
        belongs=st.checkbox('This response belongs to '+pending['supplier'])
        a,b=st.columns(2)
        draft=a.form_submit_button('Save review draft & recalculate',width='stretch')
        commit=b.form_submit_button('Commit checked quote',type='primary',width='stretch')
    if draft or commit:
        try:
            new_bids=records(bids,core.Bid); new_answers=records(answers,core.Answer); new_terms=records(terms,core.Commercial)
            for field in new_bids+new_answers: engine.invalidate_changed(field)
            if pending.get('terms_checked') and engine.canonical_hash([core.dump(t) for t in new_terms])!=engine.canonical_hash([core.dump(t) for t in ext.commercials]):
                terms_checked=False
            if pending.get('policy',{}).get('fixed_charge_checked') and fixed!=pending.get('policy',{}).get('fixed_charge_inr',0):
                fixed_checked=False
            # Treat source text as verifiable evidence for terms as well as prices/answers.
            if terms_checked:
                for term in new_terms:
                    okay,why=engine.verify_evidence(term,pending['files'])
                    if not okay: raise ValueError('Commercial term: '+why)
            problems=core.approve_review(new_bids,new_answers,{i.id for i in rfq.items},{f['name'] for f in pending['files']},all_checked,
                note.strip() or 'Buyer checked this version against the original supplier documents.',pending['files'],st.session_state.reviewer)
            revised=core.Extraction(detected_supplier=ext.detected_supplier,bids=new_bids,answers=new_answers,commercials=new_terms,warnings=ext.warnings)
            updated={**pending,'extraction':core.dump(revised),'terms_checked':terms_checked,
                'policy':{'cost_mode':w['cost_mode'],'fixed_charge_inr':fixed,'fixed_charge_checked':fixed_checked}}
            engine.validate_response(engine.Response.model_validate(updated),rfq,pending['supplier'])
            if commit:
                if not belongs: raise ValueError('Confirm that the response belongs to this supplier.')
                if pending['rfq_hash']!=core.fingerprint(w['rfq']): raise ValueError('The request changed. Restart this review.')
                previous=w['responses'].get(pending['supplier'])
                if previous:
                    w['quote_versions'].setdefault(pending['supplier'],[]).append(previous)
                    w['quote_versions'][pending['supplier']]=w['quote_versions'][pending['supplier']][-10:]
                    updated['revision']=previous.get('revision',1)+1
                w['responses'][pending['supplier']]=updated; w['pending_review']=None; w['final_selection']=None
                st.session_state.step='Compare quotes'
                rerun(w,'Quote committed',{'supplier':pending['supplier'],'evidence_warnings':problems})
            else:
                w['pending_review']=updated; rerun(w,'Review draft saved',{'evidence_warnings':problems})
        except Exception as exc: st.error('Review could not be saved: '+str(exc)[:500])
    checked=core.Extraction.model_validate(pending['extraction'])
    if checked.bids:
        preview=[]
        for bid in checked.bids:
            item=next((i for i in rfq.items if i.id==bid.line_id),None)
            n=core.normalize(bid,item,engine.effective_fx(w),cost_mode=w['cost_mode']) if item else {'price_inr':None,'status':'UNMATCHED','reason':'Choose a requested item.'}
            preview.append({'Item':item.description if item else bid.vendor_description,'INR / requested unit':n['price_inr'],'Status':n['status'],'Reason':n['reason']})
        st.write('**Saved-draft validation**'); st.dataframe(pd.DataFrame(preview),hide_index=True,width='stretch')
    if st.button('Cancel review · keep previous saved quote'):
        w['pending_review']=None; rerun(w,'Quote review canceled')

def currency_panel(w):
    currencies=sorted({b['currency'].strip().upper() for r in w['responses'].values() for b in r['extraction']['bids'] if b.get('currency')}-{'INR'})
    if not currencies: return
    with st.expander('Currency planning rates',expanded=any(not engine.rate_is_fresh(w,c) for c in currencies)):
        st.caption('Rates older than 10 days are excluded. Manually entered rates need a date and source note. Rates do not include bank charges.')
        for currency in currencies:
            ref=w['fx_reference'].get(currency,{})
            st.write(f"**{currency}** · ₹{w['fx'].get(currency,0):,.6f} · {ref.get('date','no verified date')} · {ref.get('provider','not available')}")
        if st.button('Refresh reference rates'):
            for currency in currencies:
                try:
                    ref=core.fetch_reference_rate(currency); w['fx'][currency]=ref['rate']; w['fx_reference'][currency]=ref
                    core.record(w,'FX reference refreshed',{'currency':currency,**ref})
                except Exception: st.warning(currency+': reference rate unavailable. No estimated rate was substituted.')
            rerun(w)
        with st.form('manual_fx'):
            chosen=st.selectbox('Currency',currencies)
            rate=st.number_input('INR for one currency unit',min_value=0.000001,value=float(w['fx'].get(chosen,1)),format='%.6f')
            date=st.date_input('Rate reference date',value=dt.date.today(),max_value=dt.date.today())
            note=st.text_input('Rate source / reason')
            use=st.form_submit_button('Use dated planning rate')
        if use:
            if not note.strip(): st.error('Record the source or reason for this rate.')
            elif (dt.date.today()-date).days>10: st.error('Use a rate from the last 10 days.')
            else:
                w['fx'][chosen]=rate; w['fx_reference'][chosen]={'rate':rate,'date':date.isoformat(),'provider':'Buyer entered','source':note}
                w['fx_date']=date.isoformat(); w['fx_basis']='Dated buyer planning rates'; w['final_selection']=None
                rerun(w,'FX planning rate changed',{'currency':chosen,'rate':rate,'date':date.isoformat(),'source':note})

def matrix(rfq,w,rows,allocation):
    head=['Item / specification','Requested']+w['suppliers']+['Suggested supplier']
    winner={a['line_id']:a['supplier'] for a in allocation}
    body=[]
    for item in rfq.items:
        relevant=[r for r in rows if r['line_id']==item.id]; rates=[r['price_inr'] for r in relevant if r['eligible']]
        low=min(rates) if rates else None
        cells=['<td><b>'+html.escape(item.description)+'</b><br><small>'+html.escape(item.specification)+'</small></td>', '<td>'+html.escape(f'{item.quantity:g} {item.uom}')+'</td>']
        for supplier in w['suppliers']:
            row=next((r for r in relevant if r['supplier']==supplier),None)
            best=False
            if row and row['eligible']:
                best=row['price_inr']==low; label=f"₹{row['price_inr']:,.6f}".rstrip('0').rstrip('.')+(' ★' if best else '')
            elif not row: label='Awaiting quote'
            elif row['status']=='CONFLICT': label='Conflicting quotes'
            elif row['qualification']=='DISQUALIFIED': label='Rejected'
            else: label='Not priced' if row['status']=='MISSING' else 'Needs checking'
            cells.append('<td'+(' class="best"' if best else '')+'>'+html.escape(label)+'</td>')
        cells.append('<td>'+html.escape(winner.get(item.id,'Not ready').replace('UNASSIGNED','Not ready'))+'</td>')
        body.append('<tr>'+''.join(cells)+'</tr>')
    st.markdown('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join(body)+'</tbody></table></div>',unsafe_allow_html=True)

def decision_snapshot(w):
    return core.fingerprint({'rfq':w['rfq'],'responses':w['responses'],'fx':w['fx'],'fx_date':w['fx_date'],'fx_basis':w['fx_basis']})

def quick_answer(entry,rfq,w,rows,qual,scenarios,commercials):
    index=entry['index']; facts=core.decision_facts(rfq,w,rows,qual,scenarios)
    if index in {0,1,2}:
        candidates=[('One supplier',facts['single']),('Lowest-cost split',facts['best'])] if index==2 else [('Up to two suppliers',facts['two'])] if index==1 else [('Lowest-cost split',facts['best'])]
        for title,scenario in candidates:
            if not scenario or not scenario['complete']: st.info(title+': complete checked coverage unavailable.'); continue
            st.metric(title,f"₹{scenario['spend_inr']:,.2f}")
            st.caption(('Checked landed estimate' if w['cost_mode']=='landed' else 'Goods prices only')+f" · {scenario['supplier_count']} supplier(s)")
            st.dataframe(pd.DataFrame(scenario['allocation'])[['description','supplier','quantity','uom','spend_inr']],hide_index=True)
        if index==2 and facts['savings'] is not None: st.write(f"Saving under this cost basis: ₹{facts['savings']:,.2f}.")
        if index==1 and facts['two'] and facts['two']['complete'] and facts['best']['complete']: st.write(f"Additional cost vs unrestricted split: ₹{facts['two']['spend_inr']-facts['best']['spend_inr']:,.2f}.")
    elif index==6:
        alternative=core.allocate(rfq.items,rows,[s for s in w['suppliers'] if s!=entry['supplier']],cost_mode=w['cost_mode'])
        if alternative['complete']:
            st.metric('Cost without '+entry['supplier'],f"₹{alternative['spend_inr']:,.2f}")
            st.dataframe(pd.DataFrame(alternative['allocation'])[['description','supplier','quantity','uom','spend_inr']],hide_index=True)
        else: st.warning('The remaining suppliers cannot cover the request with checked quotes.')
    elif index==7:
        st.dataframe(pd.DataFrame([{'Item':r['description'],'Supplier':r['supplier'],'Calculation':r['steps'],'INR/unit':r['price_inr'],'Status':r['status']} for r in rows if r['price_inr'] is not None]),hide_index=True)
    elif index==5:
        unchecked=[s for s,r in w['responses'].items() if not r.get('terms_checked')]
        if unchecked: st.info('Terms still need checking: '+', '.join(unchecked))
        st.dataframe(pd.DataFrame([{'Supplier':x['supplier'],'Term':x['name'],'Details':x['value']} for x in commercials]),hide_index=True)
    else: core.render_supported_answer(st,entry,rfq,w,rows,qual,scenarios,commercials)

def compare_screen(w):
    if not w['responses']: st.info('Save a supplier quote before comparing. The sample workspace is available in the sidebar.'); return
    if w['pending_review']: st.info('A replacement review is in progress. This comparison uses the previous committed quotes.')
    rfq=core.RFQ.model_validate(w['rfq'])
    currency_panel(w)
    mode=st.segmented_control('Comparison basis',['Goods prices','Landed estimate'],default='Landed estimate' if w['cost_mode']=='landed' else 'Goods prices',key='cost_basis',required=True)
    newmode='landed' if mode=='Landed estimate' else 'goods'
    if newmode!=w['cost_mode']:
        w['cost_mode']=newmode
        for response in w['responses'].values(): response['policy']['cost_mode']=newmode
        w['final_selection']=None; rerun(w,'Cost comparison basis changed',newmode)
    rows,qual,commercials=core.build_dataset(rfq,w['responses'],engine.effective_fx(w))
    scenarios=core.scenario_engine(rfq.items,rows,w['suppliers'],cost_mode=w['cost_mode'])
    facts=core.decision_facts(rfq,w,rows,qual,scenarios); best=scenarios[0]
    basis='Goods prices only; excludes tax, duty, freight and financing.' if w['cost_mode']=='goods' else 'Landed estimate: checked line tax/duty percentages, line freight and supplier fixed charges. Financing excluded.'
    st.caption(basis+' Whole line quantities are assigned to one supplier.')
    if len(w['responses'])<len(w['suppliers']): st.info('Some suppliers have not replied. These comparisons are provisional.')
    a,b,d,e=st.columns(4)
    a.metric('Checked item coverage',f"{best['covered']} / {len(rfq.items)}")
    b.metric('Quotes received',f"{len(w['responses'])} / {len(w['suppliers'])}")
    d.metric('Lowest complete cost',f"₹{best['spend_inr']:,.2f}" if best['complete'] else 'Not ready')
    e.metric('Saving vs one supplier',f"₹{facts['savings']:,.2f}" if facts['savings'] is not None else 'No benchmark')
    st.subheader('Supplier readiness')
    supplier_columns=st.columns(min(3,len(w['suppliers'])))
    labels={'READY':'Ready to compare','CHECK':'Needs checking','REJECTED':'Rejected','AWAITING':'Awaiting quote'}
    for index,supplier in enumerate(facts['suppliers']):
        with supplier_columns[index%len(supplier_columns)]:
            state=supplier['state']; css={'READY':'ready','CHECK':'check','REJECTED':'rejected','AWAITING':'awaiting'}[state]
            st.markdown('<div class="supplier-card '+css+'"><div class="state">'+labels[state]+'</div><h3>'+html.escape(supplier['supplier'])+'</h3><p>'+html.escape(' '.join(supplier['reasons']))+'</p></div>',unsafe_allow_html=True)
    if not best['complete']: st.warning('No complete buying plan is ready. Resolve missing coverage and required checks before approving an allocation.')
    st.subheader('Choose how to buy')
    cap=st.slider('Maximum suppliers in your buying plan',1,len(w['suppliers']),min(2,len(w['suppliers']))) if len(w['suppliers'])>1 else 1
    chosen=core.allocate(rfq.items,rows,w['suppliers'],cap,w['cost_mode'])
    strategycols=st.columns(3)
    for column,label,scenario in zip(strategycols,['One supplier','Up to two suppliers','Lowest-cost split'],[facts['single'],facts['two'],best]):
        with column: core.decision_card(st,label,f"₹{scenario['spend_inr']:,.2f}" if scenario and scenario['complete'] else 'Not ready',f"{scenario['supplier_count']} supplier(s) · complete scope" if scenario and scenario['complete'] else 'Complete checked coverage unavailable.','green' if label=='Lowest-cost split' else 'blue')
    if chosen['complete']:
        st.write(f"**Selected limit: {cap} supplier(s) · ₹{chosen['spend_inr']:,.2f}**")
        frame=pd.DataFrame(chosen['allocation'])
        chart=frame.groupby('supplier')['spend_inr'].sum().rename('Allocated cost (INR)')
        st.bar_chart(chart,color='#087f6d',height=200)
        st.dataframe(frame[['description','supplier','quantity','uom','goods_spend_inr','fixed_charge_inr','spend_inr']].rename(columns={'description':'Item','supplier':'Supplier','quantity':'Quantity','uom':'Unit','goods_spend_inr':'Goods (INR)','fixed_charge_inr':'Fixed charge (INR)','spend_inr':'Allocated cost (INR)'}),hide_index=True,width='stretch')
        st.download_button('Download this buying plan',core.csv_bytes(chosen['allocation']),'buying_plan.csv','text/csv')
        with st.form('final_selection'):
            confirmed=st.checkbox('I accept this allocation and have confirmed supplier terms and delivery capacity before ordering.')
            select=st.form_submit_button('Record buyer-approved plan',type='primary')
        if select:
            selected_suppliers={a['supplier'] for a in chosen['allocation']}
            if not confirmed: st.error('Confirm the final checks before recording your plan.')
            elif any(not w['responses'][s].get('terms_checked') for s in selected_suppliers): st.error('Review the commercial terms for every selected supplier first.')
            else:
                w['final_selection']={'snapshot':decision_snapshot(w),'allocation':chosen,'checked_by':st.session_state.reviewer,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat()}; rerun(w,'Buyer approved allocation',{'cap':cap,'cost_mode':w['cost_mode']})
    selection=w.get('final_selection')
    if selection and selection['snapshot']==decision_snapshot(w):
        if engine.canonical_hash(selection['allocation'])==engine.canonical_hash(chosen):
            st.success('This buying plan is buyer-approved. No orders or supplier commitments were sent.')
        else: st.info('A different buying plan is recorded as approved. The allocation currently displayed has not been approved.')
        st.download_button('Download recorded buyer-approved plan',core.csv_bytes(selection['allocation']['allocation']),'buyer_approved_plan.csv','text/csv')
    st.subheader('Prices at a glance')
    matrix(rfq,w,rows,best['allocation'])
    st.caption('★ Lowest eligible goods unit price. Landed allocations may choose a different supplier because of charges. Equal total costs prefer fewer suppliers, then supplier-name order.')
    with st.expander('Exceptions and source verification'):
        exceptions=[{'Item':r['description'],'Supplier':r['supplier'],'Status':r['status'],'Reason':r['reason'] or ('Required supplier checks have not passed.' if not r['eligible'] else '')} for r in rows if not r['eligible']]
        if exceptions: st.dataframe(pd.DataFrame(exceptions),hide_index=True)
        supplier=st.selectbox('Supplier source',list(w['responses']),key='decision_supplier')
        source_view(w['responses'][supplier]['files'],'decision_source_'+supplier)
    st.subheader('Explore your decision')
    snapshot=decision_snapshot(w)
    capabilities=core.supported_questions(rfq,w,facts,rows,commercials)
    if st.button('Generate contextual questions with AI'):
        generated=ai(lambda client,model:core.generate_contextual_questions(client,model,rfq,w,facts,rows,commercials),'Finding useful questions…')
        if generated: st.session_state.suggestions={'snapshot':snapshot,'questions':generated}
    suggestions=st.session_state.get('suggestions',{})
    prompts=suggestions.get('questions',[]) if suggestions.get('snapshot')==snapshot else capabilities[:6]
    prompt_columns=st.columns(2)
    for index,entry in enumerate(prompts):
        with prompt_columns[index%2]:
            if st.button(entry['label'],key='quick_'+entry['key'],width='stretch'): st.session_state.quick={'snapshot':snapshot,'entry':entry}
    selected=st.session_state.get('quick')
    if selected and selected['snapshot']==snapshot:
        with st.container(border=True):
            st.write('**'+selected['entry']['label']+'**'); quick_answer(selected['entry'],rfq,w,rows,qual,scenarios,commercials)
    with st.form('analyst_question'):
        query=st.text_input('Ask about your saved quotes',placeholder='Which item has the widest price spread? What terms are missing?')
        ask=st.form_submit_button('Ask analyst')
    if ask and query.strip():
        result=ai(lambda client,model:core.analyst(client,model,query,rfq,{**w,'fx':engine.effective_fx(w)},rows,qual,commercials),'Checking your saved evidence…')
        if result:
            # UI snapshot includes saved rates; analysis itself uses only fresh rates.
            result['snapshot']=snapshot; st.session_state.answer=result; w['conversation'].append(result); w['conversation']=w['conversation'][-1000:]; persist(w,'Analyst answer saved',{'operation':result['plan']['operation']})
    answer=st.session_state.get('answer')
    if answer and answer['snapshot']==snapshot:
        with st.container(border=True):
            core.render_answer_brief(st,answer,rfq)
            st.download_button('Answer figures',core.csv_bytes(answer['table']),'analyst_answer.csv','text/csv')
    with st.expander('Clarifications & decision history'):
        with st.form('clarification'):
            clarification=st.text_area('Record a supplier clarification')
            if st.form_submit_button('Save clarification') and clarification.strip():
                w['clarifications'].append({'time_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'text':clarification,'reviewer':st.session_state.reviewer}); rerun(w,'Clarification recorded')
        for note in w['clarifications'][-20:]: st.write(note['time_utc'][:10]+' · '+note['text'])
        st.caption('Clarification notes do not change eligibility until the quote and evidence are updated.')
        for previous in reversed(w['conversation'][-20:]):
            st.write('**'+previous['question']+'**'); st.write(previous['explanation']['answer']); st.caption('Historical answer · not a current recommendation')
        st.dataframe(pd.DataFrame(w['events'][-50:]),hide_index=True)
        for supplier,versions in w['quote_versions'].items(): st.caption(supplier+': '+str(len(versions))+' previous quote revision(s) retained')
    with st.expander('Exports'):
        st.download_button('Comparison audit CSV',core.csv_bytes(rows),'comparison_audit.csv','text/csv')
        st.download_button('Full comparison scenarios',json.dumps(scenarios,indent=2),'buying_scenarios.json','application/json')
        st.download_button('Analyst conversation',json.dumps(w['conversation'],indent=2),'analyst_conversation.json','application/json')

def demo_workspace():
    w=core.empty_workspace()
    rfq=core.RFQ(title='Packaging replenishment · sample',scope='Fictional demo. Shipping cartons and protective packaging.',items=[
        core.Item(id='ITEM-001',description='Shipping carton',specification='30 × 20 × 15 cm · 5 ply',quantity=200,uom='pcs',location='Bhiwandi',origin='USER PROVIDED'),
        core.Item(id='ITEM-002',description='Mailer carton',specification='22 × 16 × 8 cm',quantity=150,uom='pcs',origin='USER PROVIDED'),
        core.Item(id='ITEM-003',description='Packing tape',specification='48 mm × 50 m',quantity=80,uom='pcs',origin='USER PROVIDED'),
        core.Item(id='ITEM-004',description='Protective sheet',specification='50 × 50 cm',quantity=300,uom='pcs',origin='USER PROVIDED')],questions=[],terms=[core.Term(name='Payment',value='Agree payment and delivery before ordering.',origin='USER PROVIDED')])
    w['rfq']=core.dump(rfq); w['published']=True; w['suppliers']=['Atlas Packaging','Cedar Supply','Northline Materials']
    prices=[[42,28,55,8],[39,32,49,9],[45,26,52,7.5]]
    for supplier,rates in zip(w['suppliers'],prices):
        text='\n'.join([f'{item.id}: {item.description}; {item.specification}; INR {price} per 1 pcs' for item,price in zip(rfq.items,rates)]+['Payment: Net 30. Delivery: confirm before ordering.'])
        files=[{'name':'sample_quote.txt','data':text.encode()}]
        bids=[]
        for idx,(item,price) in enumerate(zip(rfq.items,rates),1):
            bid=core.Bid(line_id=item.id,vendor_description=item.description+' '+item.specification,price=price,currency='INR',quoted_uom='pcs',price_basis=1,file='sample_quote.txt',locator=f'Line {idx}',excerpt=text.splitlines()[idx-1],specification_checked=True,costs_checked=True)
            engine.mark_checked(bid,'Fictional demonstration data.','Demo reviewer'); bids.append(bid)
        ext=core.Extraction(detected_supplier=supplier,bids=bids,answers=[],commercials=[core.Commercial(name='Payment and delivery',value='Net 30; confirm delivery.',file='sample_quote.txt',locator='Line 5',excerpt=text.splitlines()[4])])
        response=new_pending(w,supplier,files,ext); response['terms_checked']=True; response['policy']['fixed_charge_checked']=True
        w['responses'][supplier]=response
    return w

def main():
    st.set_page_config(page_title='QuoteCompare | RFQ & Supplier Comparison',page_icon='📊',layout='wide')
    styles()
    owner,reviewer=identity(); st.session_state.owner=owner; st.session_state.reviewer=reviewer
    db=Path(os.environ.get('QUOTECOMPARE_DB',str(ROOT/'.state'/'workspaces.sqlite3'))); st.session_state.db=str(db)
    if 'work' not in st.session_state:
        try: st.session_state.work=storage.latest(db,owner) or core.empty_workspace()
        except Exception: st.warning('Saved workspace could not be loaded. Restore a private backup or start a new request.'); st.session_state.work=core.empty_workspace()
    w=st.session_state.work
    sidebar(w)
    steps=['Create request','Review quotes','Compare quotes']
    if st.session_state.get('step') not in steps: st.session_state.step='Create request'
    step=st.segmented_control('Your sourcing workflow',steps,key='step',required=True)
    header(w,step)
    {'Create request':request_screen,'Review quotes':quote_screen,'Compare quotes':compare_screen}[step](w)

