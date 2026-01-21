from PIL import Image
import random
import streamlit as st
import vertex_agent
import time
from datetime import datetime

# --- CONFIG ---
try:
    im = Image.open(r"logo.png") 
    page_icon = im
except:
    page_icon = "💊"

st.set_page_config(
    page_title="PharmaField Agent", 
    layout="wide", 
    page_icon=im
)

# --- SESSION STATE INITIALIZATION ---
if 'call_active' not in st.session_state:
    st.session_state['call_active'] = False # Default: False (Hidden on load)
if 'is_submitted' not in st.session_state:
    st.session_state['is_submitted'] = False 
if 'current_call_id' not in st.session_state:
    st.session_state['current_call_id'] = "" 

# Initialize inputs
if 'hcp_id_val' not in st.session_state:
    st.session_state['hcp_id_val'] = ""
if 'note_val' not in st.session_state:
    st.session_state['note_val'] = ""
if 'date_val' not in st.session_state:
    st.session_state['date_val'] = datetime.now()

# --- HELPER FUNCTIONS ---

def start_new_call_logic():
    """Resets everything """
    st.session_state['current_call_id'] = vertex_agent.get_next_call_id()
    st.session_state['hcp_id_val'] = "HCP_00"
    st.session_state['note_val'] = ""
    st.session_state['date_val'] = datetime.now()
    
    
    st.session_state['call_active'] = True 
    
    st.session_state['is_submitted'] = False 
    
    st.session_state.pop('last_result', None) 

def on_field_change():
    """
    Callback: If the user edits ANY field (HCP, Date, Notes), we unlock the submit button to allow an update.
    """
    if st.session_state['call_active']:
        st.session_state['is_submitted'] = False

with st.sidebar:
    st.image(r"logo.png", width=40)
    st.header("Field Configuration")
    st.markdown("---")
    
    st.markdown("### User Profile")
    rep_name = st.text_input("Rep Name", value="Sarah Jenkins")
    rep_id = st.text_input("Rep ID", value="REP_048")
    territory = st.text_input("Territory", value="Northeast - Oncology")
    
    st.markdown("---")
    
    # MAIN TRIGGER BUTTON
    if st.button(" Start New Call", type="secondary", use_container_width=True):
        start_new_call_logic()
        st.rerun()

# --- MAIN UI ---
st.title("PharmaField Intelligent CRM")
st.markdown(f"**Logged in as:** {rep_name} | **Territory:** {territory}")
st.markdown("---")

# --- VISIBILITY GATE ---
# If call_active is False (First Load), we show instructions and STOP rendering the rest.
if not st.session_state['call_active']:
    st.info(" **Action Required:** Please click 'Start New Call' in the sidebar to begin.")
    st.stop() # This halts the script here, hiding everything below.


# EVERYTHING BELOW THIS LINE IS HIDDEN UNTIL BUTTON CLICKED

# Input Form Container
with st.container():
    st.subheader("Call Details")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Call ID (System Auto-Gen)", value=st.session_state['current_call_id'], disabled=True)
    with c2:
        # Added on_change
        hcp_id = st.text_input("HCP ID", key="hcp_id_val", on_change=on_field_change)
    with c3:
        # Added key='date_val' and on_change
        call_date = st.date_input("Date", key="date_val", on_change=on_field_change, format="DD/MM/YYYY")
        
    # Added on_change
    raw_note = st.text_area("Visit Notes / Dictation", height=150, 
                           placeholder="Type notes here...", key="note_val", on_change=on_field_change)

    # BUTTON STATE Disabled if submitted=True AND user hasn't edited anything yet
    btn_disabled = st.session_state['is_submitted']
    
    # Label changes to indicate what will happen
    btn_label = " Update Record" if st.session_state.get('last_result') else "⚡ Process & Sync Call"
    
    if st.button(btn_label, type="primary", use_container_width=True, disabled=btn_disabled):
        
        if len(hcp_id) > 6 and raw_note:
            
            progress_text = "Agent is analyzing..." if not st.session_state.get('last_result') else "Updating Record..."
            my_bar = st.progress(0, text=progress_text)

            # 1. Perception
            my_bar.progress(25, text="🧠 Analyzing Medical Sentiment & Compliance...")
            
            # 2. Cognition & Action
            # The backend handles Upsert based on the ID
            result = vertex_agent.run_agent_workflow(
                st.session_state['current_call_id'], 
                hcp_id, rep_id, str(call_date), raw_note
            )
            
            if "error" in result:
                my_bar.empty()
                st.error(f"Agent Failure: {result['error']}")
            else:
                # 3. Execution Success
                my_bar.progress(100, text="✅ Database Sync Complete")
                time.sleep(0.5)
                my_bar.empty()
                
                st.session_state['last_result'] = result
                
                # LOCK THE BUTTON
                st.session_state['is_submitted'] = True 
                st.rerun()

        else:
            st.warning("Please enter a valid HCP ID (e.g. HCP_00123) and Notes.")

# --- RESULTS DISPLAY ---
# Only show if we have results (and implicitly, call is active)
if 'last_result' in st.session_state:
    res = st.session_state['last_result']
    
    st.divider()
    st.subheader(" Analysis Results")
    
    # 1. Coaching Section
    with st.container(border=True):
        st.markdown("####  Manager Coaching Tip")
        st.info(f"{res.get('coaching_tip')}")
        
        c_risk, c_sent = st.columns(2)
        with c_risk:
            if res.get("compliance_flag") == "TRUE":
                st.error(" COMPLIANCE ALERT: Risk Detected")
                st.caption("Review notes for off-label claims or adverse events.")
            else:
                st.success(" Compliance Check: PASSED")
        with c_sent:
            st.metric("HCP Sentiment", res.get("hcp_sentiment"))

    # 2. Action & Summary
    c_action, c_summary = st.columns(2)
    with c_action:
        st.markdown("####  Next Best Action")
        st.success(res.get("next_best_action"))
    with c_summary:
        st.markdown("####  Executive Summary")
        st.text_area("AI Summary", value=res.get("summary"), height=100, disabled=True, label_visibility="collapsed")

    # 3. DATABASE VIEW
    st.markdown("---")
    with st.expander("🔌 View Live CRM Database (Google Sheets Backend)"):
        st.caption("This view represents what the Home Office sees in real-time.")
        sheet = vertex_agent.get_crm_sheet()
        if sheet:
            data = sheet.get_all_records()[-5:]
            st.dataframe(data)
