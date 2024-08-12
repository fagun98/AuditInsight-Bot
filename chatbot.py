from dotenv import load_dotenv
import streamlit as st
from st_copy_to_clipboard import st_copy_to_clipboard
import warnings
import os 
from chatbot_util import get_response

# Load environment variables
load_dotenv()

# Suppress specific warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

st.set_page_config(page_title="AuditInsight-Bot", page_icon=None, layout="wide", initial_sidebar_state="expanded")

# Presuggested prompts
suggested_prompt = ["Can you give me some insight on the report of ALEXANDERS INC?", 
                    "Provide the audit findings for Microsoft Corporation.",
                    "Show me all the companies audited by Deloitte."]

# Initialize session state variables
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}  # To store all chat sessions
if "current_chat" not in st.session_state:
    st.session_state.current_chat = "Session 1"  # Default session
if "next_session_id" not in st.session_state:
    st.session_state.next_session_id = 2  # To keep track of session numbers

def save_current_chat():
    """Save the current chat and evidence into chat_sessions."""
    session_key = st.session_state.current_chat
    st.session_state.chat_sessions[session_key] = {
        "messages": st.session_state.messages.copy(),
        "evidence": st.session_state.evidence
    }

def load_chat(session_key):
    """Load a chat session by its key."""
    st.session_state.current_chat = session_key
    session_data = st.session_state.chat_sessions[session_key]
    st.session_state.messages = session_data["messages"]
    st.session_state.evidence = session_data["evidence"]

# Sidebar for switching between chat sessions
with st.sidebar:
    st.title("Chat Sessions")
    
    for session_key in st.session_state.chat_sessions.keys():
        if st.sidebar.button(session_key):
            st.session_state["session_key_clicked"] = session_key

    if st.session_state.get("session_key_clicked", False):
        save_current_chat()
        load_chat(st.session_state.session_key_clicked)
        st.session_state["session_key_clicked"] = None

    if st.sidebar.button("Start New Chat"):
        save_current_chat()  # Save the current chat before starting a new one
        new_session_key = f"Session {st.session_state.next_session_id}"
        st.session_state.next_session_id += 1
        st.session_state.messages = []
        st.session_state.evidence = None
        st.session_state["reset_evidence"] = True
        st.session_state.current_chat = new_session_key

st.header("AuditInsight-Bot")

# Display presuggested prompts
if suggested_prompt:
    with st.expander(label="Presuggested prompt", expanded=False):
        for index, prompt in enumerate(suggested_prompt):
            if st.button(prompt, key=f"suggested_prompt_{index}"):
                col1, col2 = st.columns(2)
                col1.markdown("Press the button to copy:")
                with col2:
                    st_copy_to_clipboard(prompt)

# Reset evidence button
if st.button("Regenerate the evidence"):
    st.session_state["reset_evidence"] = True

# Initialize chat history if not already loaded
if "messages" not in st.session_state:
    st.session_state.messages = []

if "evidence" not in st.session_state:
    st.session_state.evidence = None

# Display the current chat messages
for message in st.session_state.messages:
    st.chat_message('human').write(message['user'])
    st.chat_message('ai').write(message['ai'])

# Chat input and response generation
if query := st.chat_input():
    st.chat_message('human').write(query)

    if "evidence" not in st.session_state or st.session_state.get("reset_evidence", True):
        response, st.session_state.evidence = get_response(query=query, history=st.session_state.messages, records=None)
        st.session_state["reset_evidence"] = False
    else:
        response, _ = get_response(query=query, history=st.session_state.messages, records=st.session_state.evidence)

    if st.session_state.evidence:
        st.markdown("**Evidence**")
        for record in st.session_state.evidence:
            with st.expander("Evidence", expanded=False):
                st.image(record['Graph'])

    st.chat_message('ai').write(response)
    st.session_state.messages.append({'user': query, 'ai': response})