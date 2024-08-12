from dotenv import load_dotenv
import streamlit as st
from st_copy_to_clipboard import st_copy_to_clipboard
import warnings
import os 
from chatbot_util import get_response

#loading the env
load_dotenv()

# Filter out specific warning types
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

st.set_page_config(page_title="AuditInsight-Bot", page_icon=None, layout="wide", initial_sidebar_state="auto", menu_items=None)

suggested_prompt = ["Can you give me some insight on the report of ALEXANDERS INC?", 
                    "Provide the audit findings for Microsoft Corporation.",
                    "Show me all the companies audited by Deloitte."]

col1, col2, col3, col4 = st.columns(4)
st.header("AuditInsight-Bot")

if suggested_prompt:
    with st.expander(label="Presuggested prompt", expanded=False):
        for index, prompt in enumerate(suggested_prompt):
            if st.button(prompt, key=f"suggested_prompt_{index}"):
                col1, col2 = st.columns(2)
                col1.markdown("")
                col1.markdown("Press the button to copy : ")
                with col2:
                    st_copy_to_clipboard(prompt)

col1, col2 = st.columns(2)

if col1.button("Start a new chat"):
    st.session_state["reset_chat"] = True
    st.session_state["evidence"] = None
    st.session_state["reset_evidence"] = True

if col2.button("Regenerate the evidence"):
    st.session_state["reset_evidence"] = True

# Maintain chat history in session state
if "messages" not in st.session_state or st.session_state.get('reset_chat', True):
    st.session_state.messages = []
    st.session_state["reset_chat"] = False

# Iterate through each message in the session state
for i in range(len(st.session_state.messages)):
    st.chat_message('human').write(st.session_state.messages[i]['user'])
    st.chat_message('ai').write(st.session_state.messages[i]['ai'])

if query := st.chat_input():
    st.chat_message('human').write(query)
    if "messages" not in st.session_state or st.session_state.get("reset_evidence", True):
        response, st.session_state["evidence"] = get_response(query=query, history=st.session_state.messages, records=None) #'AI response'
        st.session_state["reset_evidence"] = False
    else:
        response, _  = get_response(query=query, history=st.session_state.messages, records=st.session_state.evidence) #'AI response'

    if st.session_state.evidence:
        st.markdown("**Evidence**")
        for record in st.session_state.evidence:
            with st.expander("Evidence", expanded=False):
                st.image(record['Graph'])

    st.chat_message('ai').write(response)
    st.session_state.messages.append({'user': query, 'ai': response})