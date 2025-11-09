import json
from typing import Any, Dict

import requests
import streamlit as st
from langchain_openai import ChatOpenAI
from requests.auth import HTTPBasicAuth

# -----------------------------
# Page Setup
# -----------------------------
st.set_page_config(
    page_title="Oracle Bank Assistant", page_icon="🏦", layout="centered"
)

st.markdown(
    "<h1 style='text-align: center; font-family: serif;'>🏦 Evening, KumR</h1>",
    unsafe_allow_html=True,
)
st.caption("How can I help you today?")

# -----------------------------
# Sidebar Config (Login shown only on trigger)
# -----------------------------
with st.sidebar:
    openai_key = st.text_input("🔑 OpenAI API Key", type="password")
    model_name = st.text_input("Model", value="gpt-4o")

    if "show_login" not in st.session_state:
        st.session_state.show_login = False

    if st.session_state.show_login:
        st.markdown("---")
        st.subheader("🔐 Oracle Fusion Login")
        base_url = st.text_input("Fusion Base URL (no trailing slash)", key="base_url")
        username = st.text_input("Username", key="username")
        password = st.text_input("Password", type="password", key="password")
        ignore_ssl = st.checkbox(
            "Ignore SSL verification (not recommended)", value=False, key="ignore_ssl"
        )


# -----------------------------
# Oracle REST Helpers
# -----------------------------
def banks_endpoint(url_base: str) -> str:
    return url_base.rstrip("/") + "/fscmRestApi/resources/11.13.18.05/cashBanks"


def post_bank(url: str, user: str, pwd: str, data: dict, verify_ssl: bool = True):
    headers = {
        "Content-Type": "application/vnd.oracle.adf.resourceitem+json",
        "Accept": "application/json",
    }
    return requests.post(
        url,
        auth=HTTPBasicAuth(user, pwd),
        headers=headers,
        json=data,
        timeout=60,
        verify=verify_ssl,
    )


# -----------------------------
# LLM Setup
# -----------------------------
llm = None
if openai_key:
    llm = ChatOpenAI(model=model_name, api_key=openai_key, temperature=0.4)

SYSTEM_PROMPT = (
    "You are a helpful assistant. If the user wants to create a bank, reply: 'Sure, I can help you create a bank. Let me log you in and collect the required details.'\n"
    "Then stop replying until fields are entered in UI. Otherwise, answer like a chatbot.\n"
    "Only support bank creation, no other actions."
)

# -----------------------------
# Chat State
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "bank_fields" not in st.session_state:
    st.session_state.bank_fields: Dict[str, Any] = {
        "CountryName": None,
        "BankName": None,
        "BankNumber": None,
        "BankNameAlt": None,
        "Description": None,
        "TaxpayerIdNumber": None,
    }

if "ready_to_create" not in st.session_state:
    st.session_state.ready_to_create = False

REQUIRED = ["CountryName", "BankName", "BankNumber"]

# -----------------------------
# UI Chat
# -----------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_text = st.chat_input("Type your question here…")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})

    if llm:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]
        result = llm.invoke(messages)
        reply = result.content if hasattr(result, "content") else str(result)

        if "create a bank" in user_text.lower():
            st.session_state.show_login = True
            reply = "Sure, I can help you create a bank. Let me log you in and collect the required details."
        elif any(
            k in user_text.lower() for k in ["invoice", "po", "customer", "supplier"]
        ):
            reply = "Sorry, I currently only support bank creation in Oracle Fusion."

    else:
        reply = "LLM not configured."

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()

# -----------------------------
# Show Bank Creation Form If Triggered
# -----------------------------
if st.session_state.show_login and openai_key:
    st.markdown("---")
    st.subheader("🏦 Provide Bank Details")
    st.session_state.bank_fields["CountryName"] = st.text_input("Country Name")
    st.session_state.bank_fields["BankName"] = st.text_input("Bank Name")
    st.session_state.bank_fields["BankNumber"] = st.text_input("Bank Number")
    st.session_state.bank_fields["BankNameAlt"] = st.text_input("Alternate Name")
    st.session_state.bank_fields["Description"] = st.text_input("Description")
    st.session_state.bank_fields["TaxpayerIdNumber"] = st.text_input("Taxpayer ID")

    ready = all(st.session_state.bank_fields[k] for k in REQUIRED)
    if ready and base_url and username and password:
        payload = {k: v for k, v in st.session_state.bank_fields.items() if v}
        endpoint = banks_endpoint(base_url)
        resp = post_bank(
            endpoint, username, password, payload, verify_ssl=not ignore_ssl
        )
        try:
            resp_json = resp.json()
            body_pretty = json.dumps(resp_json, indent=2)
        except Exception:
            body_pretty = resp.text

        st.success("✅ Bank creation attempted!")
        st.code(
            f"POST {endpoint}\nStatus: {resp.status_code}\n{body_pretty}",
            language="json",
        )
        st.session_state.show_login = False
        st.rerun()
