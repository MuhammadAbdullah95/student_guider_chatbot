import streamlit as st
import httpx
import uuid

# FastAPI backend URL
API_URL = "http://localhost:8000/chat"

st.set_page_config(page_title="Student Guider Chatbot", page_icon="🤖", layout="centered")
st.title("🤖 Student Guider Chatbot")

# Session state for chat history and session_id
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Chat display
st.markdown("---")
for entry in st.session_state.chat_history:
    if entry["role"] == "user":
        st.markdown(f"<div style='text-align: right; color: #2563eb; background: #e0e7ff; padding: 8px 16px; border-radius: 12px; margin: 4px 0 4px 40px;'><b>You:</b> {entry['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align: left; color: #0f172a; background: #f1f5f9; padding: 8px 16px; border-radius: 12px; margin: 4px 40px 4px 0;'><b>Bot:</b> {entry['content']}</div>", unsafe_allow_html=True)

st.markdown("---")

# User input
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message:", "", key="user_input")
    submitted = st.form_submit_button("Send")

if submitted and user_input.strip():
    # Add user message to history
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    # Prepare payload
    payload = {
        "session_id": st.session_state.session_id,
        "message": user_input
    }
    # Call FastAPI backend
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        bot_reply = data.get("response", "(No reply)")
    except Exception as e:
        bot_reply = f"Error: {e}"
    # Add bot reply to history
    st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})
    st.experimental_rerun()

# Option to reset chat
if st.button("Reset Chat"):
    st.session_state.chat_history = []
    st.session_state.session_id = str(uuid.uuid4())
    st.experimental_rerun() 