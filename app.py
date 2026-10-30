"""
Medora AI - Streamlit UI, "Heritage" design
Pages: sign-in, chat, consultation history, documents.

Run with:  uv run streamlit run app.py
Needs: medora_ai.py and auth.py in the same folder, Streamlit >= 1.40.
"""

from __future__ import annotations

import asyncio
import html as htmllib
import os
import re
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Medora AI", page_icon="🩺", layout="wide",
                   initial_sidebar_state="expanded")

_loading = st.empty()
_loading.info("Loading Medora AI… (first start can take a few seconds)")
try:
    import auth
    import medora_ai as medora

    _loading.empty()
except Exception as exc:
    _loading.empty()
    st.error("Could not import `medora_ai.py` or `auth.py`. Keep them next to `app.py`.")
    st.code("uv add streamlit openai openai-agents python-dotenv pydantic", language="bash")
    st.exception(exc)
    st.stop()

# ---------------------------------------------------------------------------
# Heritage theme: ivory canvas, forest-green sidebar, antique-gold accents
# ---------------------------------------------------------------------------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Figtree:wght@400;500;600;700&display=swap');
:root{
  --bg:#F5EFE3; --surface:#FBF8F1; --surface2:#EFE7D6; --border:#D9CFB8; --line:#BFB394;
  --text:#1F2A27; --muted:#5B6661; --green:#1E3A34;
  --gold:#B8993F; --gold-lt:#D4B56A; --gold-ink:#7A5F22; --ok:#1E5A4A;
  --danger:#9B2C3C; --shadow:0 2px 6px rgba(30,58,52,.08),0 12px 30px rgba(30,58,52,.08);
  color-scheme: light;
}
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMainBlockContainer"]{ background:var(--bg) !important; }
[data-testid="stApp"]{ color:var(--text); font-family:'Figtree','Segoe UI',system-ui,sans-serif; }
[data-testid="stHeader"]{ background:transparent; }
footer, #MainMenu{ visibility:hidden; }
.block-container{ padding:1.6rem 2rem 1rem; max-width:1600px; }
h1,h2,h3{ font-family:'Cormorant Garamond',Georgia,serif !important; color:var(--green) !important; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] td, [data-testid="stMarkdownContainer"] th,
[data-testid="stWidgetLabel"] p, label p{ color:var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *{ color:var(--muted) !important; }
code, pre{ background:var(--surface2) !important; color:var(--text) !important; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{ background:var(--green) !important; border-right:1px solid #16302A; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
section[data-testid="stSidebar"] label p{ color:#E4E9E3 !important; }
section[data-testid="stSidebar"] code{ background:rgba(255,255,255,.1) !important; color:#F5EFE3 !important; }
section[data-testid="stSidebar"] button[kind="header"] *, section[data-testid="stSidebar"] svg{ color:#E4E9E3 !important; }
.brand{ display:flex; align-items:center; gap:12px; margin:2px 0 14px; }
.brand-mark{ width:40px; height:40px; border:1.5px solid var(--gold-lt); border-radius:50%; color:var(--gold-lt);
  display:flex; align-items:center; justify-content:center; font:700 24px 'Cormorant Garamond',serif; }
.brand-name{ font:700 26px/1 'Cormorant Garamond',serif; color:#F5EFE3; }
.brand-name small{ display:block; font:500 11px 'Figtree',sans-serif; letter-spacing:.14em;
  text-transform:uppercase; color:var(--gold-lt); margin-top:4px; }
.side-label{ font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:#C9D3CC;
  font-weight:600; margin:18px 0 8px 2px; }
.fl{ display:flex; justify-content:space-between; gap:8px; font-size:12px; padding:4px 2px; color:#E4E9E3; }
.fl em{ font-style:normal; color:var(--gold-lt); }

/* ---------- buttons ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button{
  border-radius:8px; border:1px solid var(--line); background:var(--surface); min-height:44px;
  color:var(--text); font-weight:500; transition:background .15s, border-color .15s; }
.stButton > button p, .stDownloadButton > button p, .stFormSubmitButton > button p{ color:var(--text); }
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover{
  border-color:var(--gold); background:var(--surface2); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"], .stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"]{
  background:var(--green); border-color:var(--green); }
.stButton > button[kind="primary"] p, .stFormSubmitButton > button[kind="primary"] p,
.stButton > button[data-testid="stBaseButton-primary"] p,
.stFormSubmitButton > button[data-testid="stBaseButton-primaryFormSubmit"] p{ color:#F5EFE3; font-weight:600; }
section[data-testid="stSidebar"] .stButton > button{ background:transparent; border-color:rgba(255,255,255,.18);
  justify-content:flex-start; text-align:left; }
section[data-testid="stSidebar"] .stButton > button p{ color:#E4E9E3; }
section[data-testid="stSidebar"] .stButton > button:hover{ background:rgba(255,255,255,.08); border-color:var(--gold-lt); }
.st-key-del_confirm button{ border-color:var(--danger); }
.st-key-del_confirm button p{ color:var(--danger); font-weight:600; }

/* ---------- inputs ---------- */
input, textarea{ background:#fff !important; color:var(--text) !important;
  -webkit-text-fill-color:var(--text) !important; caret-color:var(--green) !important; }
input::placeholder, textarea::placeholder{ color:var(--muted) !important; -webkit-text-fill-color:var(--muted) !important; opacity:1; }
input:-webkit-autofill{ -webkit-box-shadow:0 0 0 40px #fff inset !important; -webkit-text-fill-color:var(--text) !important; }
[data-testid="stTextInput"] button svg{ color:var(--muted) !important; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div{
  background:#fff !important; border-color:var(--line) !important; border-radius:8px !important; }
[data-baseweb="select"] *{ color:var(--text) !important; }
[data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"]{ background:var(--surface) !important; }
li[role="option"]{ color:var(--text) !important; }
[data-testid="stFileUploaderDropzone"]{ background:rgba(255,255,255,.06); border:1px dashed #6E8B82; border-radius:10px; }
[data-testid="stFileUploaderDropzone"] *{ color:#D8DFD8 !important; }
[data-testid="stFileUploaderDropzone"] button{ background:var(--surface); border:1px solid var(--line); }
[data-testid="stFileUploaderDropzone"] button *{ color:var(--text) !important; }
[data-testid="stFileUploaderFile"] *{ color:#E4E9E3 !important; }
.st-key-dz [data-testid="stFileUploaderDropzone"]{ background:var(--surface); border:1px dashed var(--gold); }
.st-key-dz [data-testid="stFileUploaderDropzone"] *{ color:var(--muted) !important; }
.st-key-dz [data-testid="stFileUploaderFile"] *{ color:var(--text) !important; }
[data-testid="stAudioInput"]{ background:var(--surface2) !important; border-radius:10px; border:1px solid var(--border); }
[data-testid="stAudioInput"] button, [data-testid="stAudioInput"] button svg{ color:var(--green) !important; fill:var(--green); }
[data-testid="stExpander"]{ border:1px solid var(--border) !important; border-radius:10px; background:var(--surface); }
[data-testid="stExpander"] details{ border:none !important; background:transparent !important; }
[data-testid="stExpander"] summary *{ color:var(--text) !important; }
[data-testid="stAlert"]{ border-radius:10px; }
[data-testid="stForm"]{ border:none !important; padding:0 !important; background:transparent; }
[data-baseweb="tab-list"]{ gap:6px; border-bottom:1px solid var(--border); }
[data-baseweb="tab"] p{ color:var(--muted); font-weight:600; }
[data-baseweb="tab"][aria-selected="true"] p{ color:var(--green); }
[data-baseweb="tab-highlight"]{ background:var(--gold) !important; }
[data-testid="stRadio"] label p{ color:var(--text); font-size:14px; }

/* ---------- top bar ---------- */
.topbar{ display:flex; align-items:flex-end; justify-content:space-between; margin:0 0 1rem 2px;
  padding-bottom:14px; border-bottom:1px solid var(--border); }
.page-title{ font:700 38px/1 'Cormorant Garamond',serif; color:var(--green); }
.page-sub{ font-size:14px; color:var(--muted); margin-top:8px; }
.pills{ display:flex; gap:8px; }
.pill{ border:1px solid var(--gold); color:var(--gold-ink); border-radius:999px; padding:7px 14px;
  font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; }

/* ---------- panels ---------- */
.st-key-hist_preview, .st-key-doc_preview{
  background:var(--surface2) !important; border:1px solid var(--border) !important;
  border-radius:14px !important; box-shadow:var(--shadow); }
[class*="st-key-hc_"], [class*="st-key-hcsel_"], [class*="st-key-docrow_"], [class*="st-key-docsel_"]{
  background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:10px !important; }
[class*="st-key-hcsel_"], [class*="st-key-docsel_"]{ border-color:var(--gold) !important; box-shadow:inset 3px 0 0 var(--gold-lt); }
.grp{ font-size:11px; letter-spacing:.14em; text-transform:uppercase; font-weight:700; color:var(--muted); margin:16px 0 4px; }
.hc-t{ font:700 19px 'Cormorant Garamond',serif; color:var(--green); }
.mt{ font-size:12px; color:var(--muted); line-height:1.5; }
.tg{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:1px 9px; font-size:11px; color:var(--green); margin:4px 4px 0 0; }
.dt-t{ font-weight:600; color:var(--green); word-break:break-all; }
.th{ display:flex; gap:10px; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted);
  border-bottom:1px solid var(--border); padding:8px 6px; margin-top:10px; }
.ok{ color:var(--ok); font-weight:600; font-size:13px; }

/* ---------- chat messages ---------- */
[data-testid="stChatMessage"]{ background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:18px 22px; margin-bottom:14px; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){
  background:var(--green); border-color:var(--green); border-radius:14px 14px 2px 14px; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) *,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) *{ color:#F5EFE3 !important; }
[data-testid="stChatMessage"] table{ border-collapse:separate; border-spacing:0; border:1px solid var(--border);
  border-radius:10px; overflow:hidden; width:100%; }
[data-testid="stChatMessage"] th{ background:var(--surface2); text-align:left; }
[data-testid="stChatMessage"] th, [data-testid="stChatMessage"] td{ padding:9px 13px; border-bottom:1px solid var(--border); }
[data-testid="stChatMessage"] h1, [data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3, [data-testid="stChatMessage"] h4{
  font:700 24px/1.2 'Cormorant Garamond',serif !important; margin:0 0 6px !important; padding:0 !important; }

/* ---------- insights ---------- */
.ins-title{ font:700 26px 'Cormorant Garamond',serif; color:var(--green); margin:2px 0 12px; }
.ins-next{ background:var(--green); border-radius:10px; padding:14px 16px; margin-bottom:6px; }
.ins-next .k{ font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--gold-lt); margin-bottom:6px; font-weight:600; }
.ins-next .v{ font-size:14px; line-height:1.5; color:#F5EFE3; }
.ins-next.alert{ background:var(--danger); }
.ins-next.alert .k{ color:#F7D9DD; }
.ins-h{ font-size:11px; letter-spacing:.14em; text-transform:uppercase; font-weight:700; color:var(--muted); margin:20px 0 4px; }
.ins-row{ display:flex; align-items:center; justify-content:space-between; padding:9px 0;
  border-bottom:1px solid var(--border); font-size:14px; color:var(--text); }
.ins-row:last-child{ border-bottom:none; }
.chip{ font-size:12px; font-weight:600; border-radius:999px; padding:3px 10px; }
.chip.on{ color:var(--ok); background:#DCEBE3; }
.chip.off{ color:var(--muted); background:var(--surface); border:1px solid var(--border); }
.fine{ font-size:12px; color:var(--muted); margin-top:14px; line-height:1.5; }

/* ---------- sign-in page ---------- */
.auth-brand{ background:var(--green); color:#F5EFE3; border-radius:14px; padding:48px; min-height:640px;
  display:flex; flex-direction:column; justify-content:space-between; box-shadow:var(--shadow); }
.auth-logo{ display:flex; align-items:center; gap:12px; font:700 30px 'Cormorant Garamond',serif; }
.auth-logo span{ width:44px; height:44px; border:1.5px solid var(--gold-lt); border-radius:50%; color:var(--gold-lt);
  display:flex; align-items:center; justify-content:center; font-size:26px; }
.auth-headline{ font:700 56px/1.02 'Cormorant Garamond',serif; margin-bottom:18px; }
.auth-brand p{ color:#D8DFD8; font-size:16px; line-height:1.65; max-width:440px; margin:0; }
.auth-brand small{ color:#C9D3CC; font-size:12px; line-height:1.5; max-width:440px; }
.auth-title{ font:700 36px 'Cormorant Garamond',serif; color:var(--green); margin-top:18px; }
.auth-sub{ color:var(--muted); font-size:14px; margin-bottom:14px; }

/* ===================== Heritage design fidelity ===================== */
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stSidebarHeader"]{ display:none !important; }
.block-container{ padding:26px 36px 20px !important; max-width:none !important; }
section[data-testid="stSidebar"][aria-expanded="true"]{ width:250px !important; min-width:250px !important; }
section[data-testid="stSidebar"][aria-expanded="true"] > div{ width:250px !important; }
[data-testid="stSidebarUserContent"]{ padding:22px 16px 16px !important; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{ gap:.35rem; }
section[data-testid="stSidebar"] .st-key-new_chat button{ background:#D4B56A !important; border:none !important;
  min-height:46px; border-radius:6px; justify-content:center; }
section[data-testid="stSidebar"] .st-key-new_chat button p{ color:var(--green) !important; font-size:14px; font-weight:600; }
/* history rows: plain text, gold bar when active */
section[data-testid="stSidebar"] [class*="st-key-hia_"]{ border-left:2px solid #D4B56A; background:rgba(255,255,255,.08); }
section[data-testid="stSidebar"] [class*="st-key-hi_"] button, section[data-testid="stSidebar"] [class*="st-key-hia_"] button,
section[data-testid="stSidebar"] [class*="st-key-lnk_"] button, section[data-testid="stSidebar"] [class*="st-key-bot_"] button,
section[data-testid="stSidebar"] [class*="st-key-bot_"] [data-testid="stPopoverButton"]{
  border:none !important; background:transparent !important; min-height:0; padding:8px 10px 2px; justify-content:flex-start; }
section[data-testid="stSidebar"] [class*="st-key-hi_"] button p, section[data-testid="stSidebar"] [class*="st-key-hia_"] button p{
  color:#F5EFE3 !important; font-size:14px; line-height:1.35; }
section[data-testid="stSidebar"] [class*="st-key-lnk_"] button{ padding:6px 10px; }
section[data-testid="stSidebar"] [class*="st-key-lnk_"] button p{ color:#D4B56A !important; font-size:14px; }
section[data-testid="stSidebar"] [class*="st-key-bot_"] button p, section[data-testid="stSidebar"] [class*="st-key-bot_"] [data-testid="stPopoverButton"] p{
  color:#E4E9E3 !important; font-size:13px; }
section[data-testid="stSidebar"] [class*="st-key-bot_"] [data-testid="stPopoverButton"] svg{ display:none; }
section[data-testid="stSidebar"] [class*="st-key-bot_"] button{ padding:8px 4px; }
.hi-d{ font-size:11px; color:#9FB3AA; padding:0 10px 8px; }
/* sidebar upload zone: ONE dashed box holding a gold-outlined button + note */
.st-key-sbup{ border:1px dashed #6E8B82; border-radius:10px; padding:12px 10px 10px; }
.st-key-sbup [data-testid="stFileUploaderDropzone"]{ border:none !important; padding:0 !important; background:transparent !important; justify-content:center; }
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"], .st-key-dz [data-testid="stFileUploaderDropzoneInstructions"]{ display:none !important; }
section[data-testid="stSidebar"] [data-testid="stFileUploaderFile"], section[data-testid="stSidebar"] [data-testid="stFileUploaderPagination"]{ display:none !important; }
[data-testid="stFileUploaderDropzone"] button{ font-size:0 !important; width:100%; min-height:44px; border-radius:8px; }
[data-testid="stFileUploaderDropzone"] button *{ font-size:0 !important; }
[data-testid="stFileUploaderDropzone"] button svg{ display:none; }
[data-testid="stFileUploaderDropzone"] button::after{ content:"Upload a medical report"; font-size:14px; font-weight:600; }
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button{ background:transparent !important; border:1px solid #D4B56A !important; }
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button::after{ color:#F5EFE3; }
.st-key-dz [data-testid="stFileUploaderDropzone"] button{ background:var(--green) !important; border:none !important; width:auto; padding:0 22px; }
.st-key-dz [data-testid="stFileUploaderDropzone"] button::after{ color:#F5EFE3; }
.sb-note{ text-align:center; font-size:11px; line-height:1.55; color:#C9D3CC; margin-top:10px; }
/* sidebar footer pinned to the bottom: Settings · Account · Sign out */
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"]{ min-height:calc(100vh - 40px); }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"] > div:has(.st-key-sbbot){ margin-top:auto; }
section[data-testid="stSidebar"] .st-key-lnk_rm button::before, section[data-testid="stSidebar"] .st-key-bot_acc [data-testid="stPopoverButton"]::before,
section[data-testid="stSidebar"] .st-key-bot_out button::before{ content:"· "; color:#E4E9E3; margin-right:4px; }

/* messages: no avatars; assistant card left, user bubble right */
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"], [data-testid="stChatMessageAvatarCustom"]{ display:none !important; }
[data-testid="stChatMessage"]{ margin-right:14%; margin-left:0; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){ margin-left:38%; margin-right:0; padding:14px 20px; }
.ag{ font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--gold-ink); font-weight:600; margin-bottom:6px; }
.illus-cap{ font-size:12px; color:var(--muted); line-height:1.5; padding-top:6px; }
[class*="st-key-act_"] button{ min-height:34px; padding:0 14px; border-radius:6px; background:transparent; border:1px solid var(--line); }
[class*="st-key-act_"] button p{ font-size:12px; color:var(--green); }

/* ---------- bottom dock: suggestion pills + composer ---------- */
.st-key-dock{ margin-top:4px; }
.st-key-dock [data-testid="stVerticalBlock"]{ gap:.6rem; }
.st-key-chips .stButton > button, .st-key-chips .stDownloadButton > button{
  background:transparent !important; border:1px solid var(--gold) !important; border-radius:999px !important;
  min-height:38px; padding:0 14px; }
.st-key-chips button p{ color:#5E4A18 !important; font-size:13px; font-weight:500; }
.st-key-chips button:hover{ background:var(--surface2) !important; }
.st-key-composer [data-testid="stForm"]{ border:1px solid var(--gold-lt) !important; border-radius:12px !important;
  padding:8px 10px !important; background:var(--surface) !important; }
.st-key-composer [data-testid="stForm"] [data-testid="stHorizontalBlock"]{ align-items:center; gap:.6rem; }
.st-key-composer [data-baseweb="input"], .st-key-composer [data-baseweb="base-input"]{
  border:none !important; background:transparent !important; box-shadow:none !important; }
.st-key-composer input{ background:transparent !important; font-size:15px; }
[data-testid="InputInstructions"]{ display:none !important; }
.st-key-composer [data-testid="stPopoverButton"]{ background:var(--surface) !important; border:1px solid var(--line) !important;
  border-radius:8px !important; min-height:44px; width:100%; justify-content:center; }
.st-key-composer [data-testid="stPopoverButton"] p{ color:var(--text) !important; font-size:14px; font-weight:500; }
.st-key-composer [data-testid="stPopoverButton"] svg{ display:none; }
.st-key-composer [data-testid="stPopoverButton"]:hover{ border-color:var(--gold) !important; background:var(--surface2) !important; }
.st-key-composer .stFormSubmitButton > button{ background:var(--green) !important; border-color:var(--green) !important; }
.st-key-composer .stFormSubmitButton > button p{ color:var(--gold-lt) !important; font-weight:600; }
/* contents of the Attach / Voice popovers */
[data-testid="stPopoverBody"]{ min-width:340px; }
[data-testid="stPopoverBody"] [data-testid="stFileUploaderDropzone"]{ background:var(--surface); border:1px dashed var(--gold); }
[data-testid="stPopoverBody"] [data-testid="stFileUploaderDropzone"] *{ color:var(--muted) !important; }
[data-testid="stPopoverBody"] [data-testid="stFileUploaderDropzone"] button{ background:var(--green) !important; border:none !important; width:auto; padding:0 20px; }
[data-testid="stPopoverBody"] [data-testid="stFileUploaderDropzone"] button::after{ content:"Browse reports"; color:#F5EFE3 !important; }
[data-testid="stPopoverBody"] [data-testid="stFileUploaderFile"] *{ color:var(--text) !important; }

/* insights: fixed full-height sand column on the right */
.st-key-insights{ position:fixed !important; top:0; right:0; bottom:0; width:300px; background:var(--surface2) !important;
  border:none !important; border-left:1px solid var(--border) !important; border-radius:0 !important; box-shadow:none !important;
  padding:26px 22px !important; overflow-y:auto; z-index:5; }
.ins-row{ padding:7px 0; font-size:13.5px; }
.chip{ font-style:normal; font-size:13px; font-weight:600; padding:0; background:none !important; border:none !important; border-radius:0; }
.chip.on{ color:var(--ok) !important; } .chip.off{ color:var(--muted) !important; }

/* ===================== v3 fixes ===================== */
/* message cards: own containers instead of st.chat_message (no avatar, no theme surprises) */
[class*="st-key-ma_"]{ background:var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:18px 22px; margin:0 12% 14px 0; }
[class*="st-key-mu_"]{ background:var(--green); border-radius:14px 14px 2px 14px; padding:14px 20px;
  margin:0 0 14px auto; width:fit-content; max-width:62%; }
[class*="st-key-mu_"] *{ color:#F5EFE3 !important; }
[class*="st-key-ma_"] h1, [class*="st-key-ma_"] h2, [class*="st-key-ma_"] h3, [class*="st-key-ma_"] h4{
  font:700 24px/1.2 'Cormorant Garamond',serif !important; margin:0 0 6px !important; padding:0 !important; }
[class*="st-key-ma_"] table{ border-collapse:separate; border-spacing:0; border:1px solid var(--border);
  border-radius:10px; overflow:hidden; width:100%; }
[class*="st-key-ma_"] th{ background:var(--surface2); text-align:left; }
[class*="st-key-ma_"] th, [class*="st-key-ma_"] td{ padding:9px 13px; border-bottom:1px solid var(--border); }
/* scrolling message area fills the window (composer stays visible underneath) */
.st-key-msgs{ height:calc(100vh - 345px) !important; min-height:260px; }

/* composer: force a light input (the dark box hid the typed prompt) */
.st-key-composer [data-testid="stTextInputRootElement"], .st-key-composer [data-baseweb="input"],
.st-key-composer [data-baseweb="base-input"], .st-key-composer input{
  background:var(--surface) !important; color:var(--text) !important; -webkit-text-fill-color:var(--text) !important;
  border:none !important; box-shadow:none !important; }
.st-key-composer input::placeholder{ color:var(--muted) !important; -webkit-text-fill-color:var(--muted) !important; }

/* popover buttons: no chevron glyph, never wrap */
[data-testid="stPopoverButton"] svg, [data-testid="stPopoverButton"] [data-testid="stIconMaterial"],
[data-testid="stPopover"] button svg, [data-testid="stPopover"] button [data-testid="stIconMaterial"]{ display:none !important; }
[data-testid="stPopoverButton"] p, [data-testid="stPopover"] button p{ white-space:nowrap; }
/* popover panel (Attach / Voice / Settings / Account): light card */
[data-testid="stPopoverBody"]{ background:var(--surface) !important; border:1px solid var(--border) !important;
  border-radius:12px !important; padding:16px !important; }
[data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p, [data-testid="stPopoverBody"] label p{ color:var(--text) !important; }
[data-testid="stAudioInput"]{ background:var(--surface2) !important; }

/* sidebar polish */
section[data-testid="stSidebar"] [class*="st-key-hi_"], section[data-testid="stSidebar"] [class*="st-key-hia_"]{ padding-bottom:6px; }
.st-key-sbup{ padding:12px 10px 16px !important; }
.st-key-sbup [data-testid="stVerticalBlock"]{ gap:.5rem; }
.sb-note{ margin:0 !important; }
section[data-testid="stSidebar"] [class*="st-key-bot_"] button,
section[data-testid="stSidebar"] [class*="st-key-bot_"] [data-testid="stPopoverButton"]{ padding:6px 2px !important; white-space:nowrap; }
"""
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sign-in gate: nothing below runs until a user is signed in
# ---------------------------------------------------------------------------
user = auth.require_login()
UID = user["id"]


# ---------------------------------------------------------------------------
# Background worker (Agents SDK needs an asyncio loop)
# ---------------------------------------------------------------------------
def _init_worker() -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())


@st.cache_resource
def get_worker() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="medora", initializer=_init_worker)


def run_in_worker(fn, *args, **kwargs):
    return get_worker().submit(lambda: fn(*args, **kwargs)).result()


# ---------------------------------------------------------------------------
# Constants + helpers
# ---------------------------------------------------------------------------
VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"]
LANGS = {"Auto-detect": None, "English": "en", "Urdu": "ur", "Hindi": "hi",
         "Arabic": "ar", "Spanish": "es", "French": "fr", "German": "de"}
DOC_TYPES = ["pdf", "txt", "md", "docx", "doc", "pptx", "json", "html", "csv"]
IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]  # photos / screenshots of a report (read by a vision model)
UPLOAD_TYPES = DOC_TYPES + IMAGE_TYPES
WELCOME = (
    "Hi, I'm **Medora AI**, an educational healthcare assistant. I can explain medical "
    "terms and conditions, walk through an uploaded (de-identified) lab report, share "
    "general wellness information, create generic educational illustrations, and talk "
    "with you by voice.\n\nI can't diagnose or change treatment, so please check personal "
    "health concerns with a qualified clinician."
)
IMAGE_RE = re.compile(r"[`*]*IMAGE_PATH:\s*(.+?\.png)[`*]*", re.IGNORECASE)
AGENT_TOOLS = {
    "Medical Information Agent": "Web search",
    "Medical Report Analysis Agent": "Report search",
    "Wellness Agent": "Web search",
}


def h(markup: str) -> None:
    clean = "\n".join(line.strip() for line in markup.splitlines() if line.strip())
    st.markdown(clean, unsafe_allow_html=True)


def esc(text: str) -> str:
    return htmllib.escape(str(text))


def panel(key: str):
    try:
        return st.container(border=True, key=key)
    except TypeError:
        return st.container(border=True)


def bx(key: str):
    """Borderless keyed container (for CSS hooks); falls back on older Streamlit versions."""
    try:
        return st.container(key=key)
    except TypeError:
        return st.container()


def extract_images(text: str) -> tuple[str, list[str]]:
    paths = []
    for match in IMAGE_RE.finditer(text or ""):
        path = match.group(1).strip().strip("`\"'")
        if Path(path).exists():
            paths.append(path)
    return IMAGE_RE.sub("", text or "").strip(), paths


def agent_label(name: str | None, images: list[str], emergency: bool = False) -> str:
    """Header line of an answer card, e.g. 'Medical Information Agent · Web search'."""
    if emergency:
        return "Emergency screen"
    if images:
        return "Medora AI Coordinator · Image generation"
    if not name:
        return "Medora AI"
    tool = AGENT_TOOLS.get(name)
    return f"{name} · {tool}" if tool else name


def make_message(role: str, content: str, **extra) -> dict:
    return {"role": role, "content": content, "images": [], "audio": None,
            "emergency": False, "agent": None, "ts": time.time(), **extra}


def is_empty_chat(c: dict) -> bool:
    return len(c["messages"]) <= 1 and not c["files"]


def updated(c: dict) -> float:
    return c["messages"][-1].get("ts", c["created"]) if c["messages"] else c["created"]


def fmt_when(ts: float) -> str:
    d, now = datetime.fromtimestamp(ts), datetime.now()
    clock = d.strftime("%I:%M %p").lstrip("0").lower()
    days = (now.date() - d.date()).days
    if days == 0:
        return f"Today, {clock}"
    if days == 1:
        return f"Yesterday, {clock}"
    return d.strftime("%a %d %b")


def group_of(ts: float) -> str:
    days = (datetime.now().date() - datetime.fromtimestamp(ts).date()).days
    return "Today" if days == 0 else "Yesterday" if days == 1 else "Earlier this week" if days < 7 else "Older"


def size_fmt(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


def ext_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def has_images(c: dict) -> bool:
    return any(m.get("images") for m in c["messages"])


def has_voice(c: dict) -> bool:
    return any(m["role"] == "user" and m["content"].startswith("🎙️") for m in c["messages"])


def summary_line(c: dict) -> str:
    first = next((m["content"] for m in c["messages"] if m["role"] == "user"), "")
    first = first.replace("\n", " ").strip()
    return (first[:110] + "…") if len(first) > 110 else (first or "No messages yet")


def transcript_text(c: dict) -> str:
    lines = [f"Medora AI conversation - {c['title']}", ""]
    for m in c["messages"]:
        lines += [f"{'You' if m['role'] == 'user' else 'Medora AI'}: {m['content']}", ""]
    lines.append(medora.DISCLAIMER)
    return "\n".join(lines)


def greeting(name: str) -> str:
    hour = time.localtime().tm_hour
    part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
    parts = name.split() or ["there"]
    first = next((t for t in parts if len(t.strip(".")) > 1), parts[0])
    if first.isupper():
        first = first.capitalize()
    return f"Good {part}, {first}"


# ---------------------------------------------------------------------------
# Chat + document state operations
# ---------------------------------------------------------------------------
def new_chat() -> str:
    cur = st.session_state.chats.get(st.session_state.get("active"))
    if cur and is_empty_chat(cur):  # reuse an untouched consultation instead of piling up empty ones
        st.session_state.page = "chat"
        return cur["id"]
    cid = uuid.uuid4().hex[:12]
    st.session_state.chats[cid] = {
        "id": cid, "title": "New chat", "created": time.time(),
        "messages": [make_message("assistant", WELCOME, welcome=True)],
        "vs_id": None, "files": [], "processed": set(), "uploader_n": 0, "summary": [],
    }
    st.session_state.active = cid
    st.session_state.page = "chat"
    auth.save_chat(UID, st.session_state.chats[cid])
    return cid


def open_chat(cid: str) -> None:
    st.session_state.active = cid
    st.session_state.page = "chat"
    st.rerun()


def delete_chat(cid: str) -> None:
    c = st.session_state.chats.get(cid)
    if not c:
        return
    if c["vs_id"] or c["files"]:
        try:
            run_in_worker(medora.delete_document_collection, c["vs_id"], [f["id"] for f in c["files"]])
        except Exception:
            pass
    try:  # wipe the persisted agent memory for this consultation
        con = sqlite3.connect(medora.DB_PATH)
        with con:
            con.execute("DELETE FROM agent_messages WHERE session_id = ?", (cid,))
            con.execute("DELETE FROM agent_sessions WHERE session_id = ?", (cid,))
        con.close()
    except Exception:
        pass
    auth.delete_chat_row(UID, cid)
    del st.session_state.chats[cid]
    if st.session_state.chats:
        st.session_state.active = max(st.session_state.chats.values(), key=updated)["id"]
    else:
        st.session_state.active = None
        new_chat()


def image_to_text(name: str, data: bytes) -> str:
    """File Search cannot index pictures, so a vision model transcribes the report image to plain text first."""
    import base64
    ext = ext_of(name)
    mime = "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"
    b64 = base64.b64encode(data).decode()
    resp = medora.get_client().responses.create(
        model=medora.MODEL,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": (
                "Transcribe all text and tables in this medical report image exactly as written, "
                "keeping test names, values, units and reference ranges together. Do not interpret, "
                "diagnose or add anything. If part of it is unreadable, write [unreadable].")},
            {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
        ]}],
    )
    return (resp.output_text or "").strip()


def index_files(c: dict, files) -> int:
    """Upload + index files into the consultation's vector store (File Search). Returns how many were new."""
    fresh = [f for f in files if f"{f.name}:{f.size}" not in c["processed"]]
    if not fresh:
        return 0
    with st.spinner("Indexing document for File Search…"):
        try:
            if not c["vs_id"]:
                c["vs_id"] = run_in_worker(medora.create_vector_store, f"medora-{c['id']}")
            for f in fresh:
                up_name, up_data = f.name, f.getvalue()
                if ext_of(up_name) in IMAGE_TYPES:  # picture -> transcribed text file for File Search
                    text = run_in_worker(image_to_text, up_name, up_data)
                    if not text:
                        raise ValueError(f"No readable text found in {up_name}.")
                    up_name, up_data = up_name.rsplit(".", 1)[0] + ".txt", text.encode("utf-8")
                file_id = run_in_worker(medora.add_document, c["vs_id"], up_name, up_data)
                c["files"].append({"name": f.name, "id": file_id, "size": f.size, "ts": time.time()})
                c["processed"].add(f"{f.name}:{f.size}")
            st.toast(f"Indexed {len(fresh)} document(s).", icon="📄")
        except Exception as exc:
            st.session_state.flash = f"Could not index the document: {exc}"
            return 0
    auth.save_chat(UID, c)
    return len(fresh)


def upload_widget(c: dict, suffix: str) -> None:
    """Standalone uploader (sidebar / Documents page). Indexes, then resets itself so no file chip lingers."""
    uploads = st.file_uploader("Upload a medical report", type=UPLOAD_TYPES, accept_multiple_files=True,
                               key=f"uploader_{suffix}_{c['id']}_{c['uploader_n']}",
                               label_visibility="collapsed")
    if uploads:
        index_files(c, uploads)
        c["uploader_n"] += 1
        st.rerun()


def remove_one_file(c: dict, file_id: str) -> None:
    def _do():
        client = medora.get_client()
        if c["vs_id"]:
            try:
                client.vector_stores.files.delete(vector_store_id=c["vs_id"], file_id=file_id)
            except Exception:
                pass
        try:
            client.files.delete(file_id)
        except Exception:
            pass

    with st.spinner("Removing document…"):
        run_in_worker(_do)
        gone = next((f for f in c["files"] if f["id"] == file_id), None)
        c["files"] = [f for f in c["files"] if f["id"] != file_id]
        if gone:
            c["processed"].discard(f"{gone['name']}:{gone['size']}")
        if not c["files"] and c["vs_id"]:  # nothing left: drop the empty vector store too
            try:
                run_in_worker(medora.delete_document_collection, c["vs_id"], [])
            except Exception:
                pass
            c["vs_id"] = None
        c["uploader_n"] += 1


def remove_all_files(c: dict) -> None:
    with st.spinner("Removing documents…"):
        try:
            run_in_worker(medora.delete_document_collection, c["vs_id"], [f["id"] for f in c["files"]])
        except Exception:
            pass
    c.update(vs_id=None, files=[], processed=set(), uploader_n=c["uploader_n"] + 1)


def current_voice() -> str:
    return st.session_state.get("voice_sel") or (medora.TTS_VOICE if medora.TTS_VOICE in VOICES else "alloy")


def current_lang() -> str | None:
    return LANGS.get(st.session_state.get("lang_sel", "Auto-detect"))


# ---------------------------------------------------------------------------
# Per-user session state (reloaded when a different person signs in)
# ---------------------------------------------------------------------------
if st.session_state.get("uid") != UID:
    st.session_state.uid = UID
    st.session_state.chats = auth.load_chats(UID)
    for _cid in [k for k, v in st.session_state.chats.items() if is_empty_chat(v)]:
        auth.delete_chat_row(UID, _cid)  # drop untouched "New chat" leftovers
        del st.session_state.chats[_cid]
    st.session_state.read_aloud = False
    st.session_state.page = "chat"
    st.session_state.active = None
    if st.session_state.chats:
        st.session_state.active = max(st.session_state.chats.values(), key=updated)["id"]
    else:
        new_chat()

chat = st.session_state.chats[st.session_state.active]
page = st.session_state.get("page", "chat")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    h(
        """
        <div class="brand">
          <div class="brand-mark">M</div>
          <div class="brand-name">Medora<small>Health companion</small></div>
        </div>
        """
    )
    if st.button("New consultation", use_container_width=True, key="new_chat"):
        new_chat()
        st.rerun()

    h('<div class="side-label">Consultation history</div>')
    listed = [c for c in sorted(st.session_state.chats.values(), key=updated, reverse=True)
              if not is_empty_chat(c) or c["id"] == chat["id"]][:3]
    for c in listed:
        active = c["id"] == chat["id"] and page == "chat"
        title = c["title"] if len(c["title"]) <= 34 else c["title"][:33] + "…"
        with bx(f"{'hia' if active else 'hi'}_{c['id']}"):
            if st.button(title, key=f"chat_{c['id']}", use_container_width=True):
                st.session_state.active = c["id"]
                st.session_state.page = "chat"
                st.rerun()
            h(f'<div class="hi-d">{esc(fmt_when(updated(c)))}</div>')
    with bx("lnk_hist"):
        if st.button("View all history", key="view_hist"):
            st.session_state.page = "history"
            st.rerun()

    h('<div class="side-label">Your documents</div>')
    with bx("sbup"):
        if page != "documents":  # the Documents page has its own upload area
            upload_widget(chat, "side")
        h('<div class="sb-note">PDF, DOCX, TXT, MD, CSV, JSON, HTML, PPTX, PNG, JPG<br>De-identified reports only</div>')
    for f in chat["files"]:
        h(f'<div class="fl"><span>{esc(f["name"])}</span><em>Indexed</em></div>')
    d1, d2 = st.columns([2.3, 1])
    with d1, bx("lnk_docs"):
        if st.button("View all documents", key="view_docs"):
            st.session_state.page = "documents"
            st.rerun()
    if chat["files"]:
        with d2, bx("lnk_rm"):
            if st.button("Remove", key="rm_docs"):
                remove_all_files(chat)
                st.rerun()

    with bx("sbbot"):
        b1, b2, b3 = st.columns([1, 1, 1.1], gap="small")
        with b1, bx("bot_set"):
            with st.popover("Settings"):
                st.selectbox("Voice for replies", VOICES,
                             index=VOICES.index(medora.TTS_VOICE) if medora.TTS_VOICE in VOICES else 0, key="voice_sel")
                st.selectbox("Speech language", list(LANGS), key="lang_sel")
                st.caption(f"Tracing: {'on' if medora.DEFAULT_TRACING else 'off'} · "
                           f"Debug logs: {'on' if medora.DEBUG_LOGS else 'off'}")
        with b2, bx("bot_acc"):
            with st.popover("Account"):
                auth.render_account_settings(user)
        with b3, bx("bot_out"):
            if st.button("Sign out", key="sign_out"):
                auth.sign_out()

if not os.getenv("OPENAI_API_KEY"):
    st.warning("OPENAI_API_KEY was not found. Add `OPENAI_API_KEY=sk-...` to a `.env` file "
               "next to app.py, then restart Streamlit.")
if flash := st.session_state.pop("flash", None):
    st.error(flash)


# ---------------------------------------------------------------------------
# Page: consultation history
# ---------------------------------------------------------------------------
def render_history() -> None:
    all_c = sorted((c for c in st.session_state.chats.values() if not is_empty_chat(c)),
                   key=updated, reverse=True)
    n = len(all_c)
    h(f"""
        <div class="topbar"><div>
          <div class="page-title">Consultation history</div>
          <div class="page-sub">Every consultation is saved to your account and can be reopened.</div>
        </div><div class="pills"><span class="pill">{n} consultation{'s' if n != 1 else ''}</span></div></div>
    """)
    q = st.text_input("Search your consultations", key="hist_q", label_visibility="collapsed",
                      placeholder="Search your consultations…").strip().lower()
    flt = st.radio("Filter", ["All", "With documents", "With images", "Voice"], horizontal=True,
                   key="hist_f", label_visibility="collapsed")

    def match(c: dict) -> bool:
        if q and q not in c["title"].lower() and not any(q in m["content"].lower() for m in c["messages"]):
            return False
        return (flt == "All" or (flt == "With documents" and c["files"])
                or (flt == "With images" and has_images(c)) or (flt == "Voice" and has_voice(c)))

    shown = [c for c in all_c if match(c)]
    if not shown:
        st.info("No consultations match. Start a new consultation to begin your history.")
        return
    sel_id = st.session_state.get("hist_sel")
    if sel_id not in {c["id"] for c in shown}:
        sel_id = shown[0]["id"]

    left, right = st.columns([2, 1.05], gap="large")
    with left:
        last = None
        for c in shown:
            g = group_of(updated(c))
            if g != last:
                h(f'<div class="grp">{esc(g)}</div>')
                last = g
            with panel(f"{'hcsel' if c['id'] == sel_id else 'hc'}_{c['id']}"):
                a, b, d = st.columns([5, 1.1, 1])
                tags = "".join(f'<span class="tg">{esc(t)}</span>' for t in (
                    [f"{len(c['files'])} document{'s' if len(c['files']) != 1 else ''}"] * bool(c["files"])
                    + ["Image"] * has_images(c) + ["Voice"] * has_voice(c)))
                a.markdown(
                    f'<div class="hc-t">{esc(c["title"])}</div>'
                    f'<div class="mt">{esc(summary_line(c))}<br>{esc(fmt_when(updated(c)))} · '
                    f'{len(c["messages"]) - 1} messages</div>{tags}', unsafe_allow_html=True)
                if b.button("Preview", key=f"prev_{c['id']}"):
                    st.session_state.hist_sel = c["id"]
                    st.rerun()
                if d.button("Open", key=f"open_{c['id']}", type="primary"):
                    open_chat(c["id"])

    with right:
        c = next(x for x in shown if x["id"] == sel_id)
        with panel("hist_preview"):
            h(f'<div class="ins-title">{esc(c["title"])}</div>'
              f'<div class="mt">{esc(fmt_when(updated(c)))} · {len(c["messages"]) - 1} messages</div>')
            h('<div class="ins-h">Visit summary</div>')
            if c["summary"]:
                for item in c["summary"][-5:]:
                    st.markdown(f"- {item}")
            else:
                st.caption("Nothing yet. Use “Add to summary” on an answer in the chat.")
            h('<div class="ins-h">Documents in this consultation</div>')
            if c["files"]:
                for f in c["files"]:
                    h(f'<div class="ins-row"><span>{esc(f["name"])}</span><span class="chip on">Indexed</span></div>')
            else:
                st.caption("None attached.")
            h('<div class="ins-h">Last exchange</div>')
            last_u = next((m for m in reversed(c["messages"]) if m["role"] == "user"), None)
            last_a = next((m for m in reversed(c["messages"]) if m["role"] == "assistant" and not m.get("welcome")), None)
            if last_u:
                st.markdown(f"**You:** {last_u['content'][:160]}")
            if last_a:
                st.markdown(f"**Medora:** {last_a['content'][:200]}{'…' if len(last_a['content']) > 200 else ''}")
            if st.button("Open consultation", key="hp_open", type="primary", use_container_width=True):
                open_chat(c["id"])
            st.download_button("Export chat", data=transcript_text(c), file_name=f"medora_{c['id']}.txt",
                               mime="text/plain", use_container_width=True, key=f"hp_exp_{c['id']}")
            if st.session_state.get("confirm_del") == c["id"]:
                st.warning("This deletes the consultation and its documents.")
                x, y = st.columns(2)
                if x.button("Delete", key="del_confirm", use_container_width=True):
                    st.session_state.pop("confirm_del", None)
                    delete_chat(c["id"])
                    st.rerun()
                if y.button("Cancel", key="del_cancel", use_container_width=True):
                    st.session_state.pop("confirm_del", None)
                    st.rerun()
            elif st.button("Delete consultation", key="hp_del", use_container_width=True):
                st.session_state.confirm_del = c["id"]
                st.rerun()


# ---------------------------------------------------------------------------
# Page: documents
# ---------------------------------------------------------------------------
def ask_about(c: dict, f: dict) -> None:
    st.session_state.active = c["id"]
    st.session_state.page = "chat"
    st.session_state.pending = f"Explain the uploaded document “{f['name']}” in plain language."
    st.rerun()


def render_documents() -> None:
    head_slot = st.empty()
    with panel("dz"):
        st.caption(f"New files are added to: {chat['title']}. "
                   "Supported: PDF, DOCX, TXT, MD, CSV, JSON, HTML, PPTX, PNG, JPG. De-identified or synthetic reports only.")
        upload_widget(chat, "docs")

    rows = sorted(((c, f) for c in st.session_state.chats.values() for f in c["files"]),
                  key=lambda r: r[1].get("ts", 0), reverse=True)
    total = sum(f.get("size", 0) for _, f in rows)
    head_slot.markdown(
        f'<div class="topbar"><div><div class="page-title">Your documents</div>'
        f'<div class="page-sub">Every file you have uploaded, across all consultations, indexed for report search.</div></div>'
        f'<div class="pills"><span class="pill">{len(rows)} document{"s" if len(rows) != 1 else ""} · {size_fmt(total)}</span></div></div>',
        unsafe_allow_html=True)

    q = st.text_input("Search your documents", key="doc_q", label_visibility="collapsed",
                      placeholder="Search your documents…").strip().lower()
    flt = st.radio("Type", ["All", "PDF", "DOCX", "TXT", "Other"], horizontal=True,
                   key="doc_f", label_visibility="collapsed")

    def kind(name: str) -> str:
        e = ext_of(name)
        return "PDF" if e == "pdf" else "DOCX" if e in {"docx", "doc"} else "TXT" if e in {"txt", "md"} else "Other"

    shown = [(c, f) for c, f in rows if (not q or q in f["name"].lower()) and (flt == "All" or kind(f["name"]) == flt)]
    if not shown:
        st.info("No documents yet. Upload a de-identified report above to get a plain-language walkthrough.")
        return
    sel_id = st.session_state.get("doc_sel")
    if sel_id not in {f["id"] for _, f in shown}:
        sel_id = shown[0][1]["id"]

    left, right = st.columns([2.3, 1], gap="large")
    with left:
        h('<div class="th"><span style="flex:2.2">Document</span><span style="flex:1.2">Uploaded</span>'
          '<span style="flex:1.7">Consultation</span><span style="flex:.8">Status</span><span style="flex:1.7"></span></div>')
        for c, f in shown:
            with panel(f"{'docsel' if f['id'] == sel_id else 'docrow'}_{f['id']}"):
                cols = st.columns([2.2, 1.2, 1.7, 0.8, 0.85, 0.85])
                cols[0].markdown(f'<div class="dt-t">{esc(f["name"])}</div>'
                                 f'<div class="mt">{kind(f["name"])} · {size_fmt(f.get("size", 0))}</div>',
                                 unsafe_allow_html=True)
                cols[1].markdown(f'<div class="mt">{esc(fmt_when(f["ts"])) if f.get("ts") else "-"}</div>',
                                 unsafe_allow_html=True)
                cols[2].markdown(f'<div class="mt">{esc(c["title"])}</div>', unsafe_allow_html=True)
                cols[3].markdown('<span class="ok">Indexed</span>', unsafe_allow_html=True)
                if cols[4].button("Details", key=f"det_{f['id']}"):
                    st.session_state.doc_sel = f["id"]
                    st.rerun()
                if cols[5].button("Ask", key=f"ask_{f['id']}", type="primary"):
                    ask_about(c, f)

    with right:
        c, f = next((c, f) for c, f in shown if f["id"] == sel_id)
        with panel("doc_preview"):
            h(f'<div class="ins-title" style="word-break:break-all">{esc(f["name"])}</div>'
              f'<div class="mt">{kind(f["name"])} · {size_fmt(f.get("size", 0))}'
              f'{" · uploaded " + esc(fmt_when(f["ts"])) if f.get("ts") else ""}</div>')
            h('<div class="ins-h">Status</div><div class="ins-row"><span>File Search</span>'
              '<span class="chip on">Indexed</span></div>')
            h(f'<div class="ins-h">Used in</div><div class="ins-row"><span>{esc(c["title"])}</span></div>')
            if st.button("Open consultation", key="dp_open", use_container_width=True):
                open_chat(c["id"])
            h('<div class="ins-h">Try asking</div>')
            st.caption("“Explain my uploaded report in plain language.”")
            if st.button("Ask Medora about this report", key="dp_ask", type="primary", use_container_width=True):
                ask_about(c, f)
            if st.session_state.get("confirm_doc") == f["id"]:
                st.warning("This removes the document from report search for its consultation.")
                x, y = st.columns(2)
                if x.button("Remove", key="del_confirm", use_container_width=True):
                    st.session_state.pop("confirm_doc", None)
                    remove_one_file(c, f["id"])
                    st.rerun()
                if y.button("Cancel", key="doc_cancel", use_container_width=True):
                    st.session_state.pop("confirm_doc", None)
                    st.rerun()
            elif st.button("Remove document", key="dp_rm", use_container_width=True):
                st.session_state.confirm_doc = f["id"]
                st.rerun()


# ---------------------------------------------------------------------------
# Page: chat
# ---------------------------------------------------------------------------
def render_message(i: int, msg: dict) -> None:
    role = msg["role"]
    with bx(f"{'mu' if role == 'user' else 'ma'}_{i}"):
        if role == "assistant":
            h(f'<div class="ag">{esc(msg.get("agent") or "Medora AI")}</div>')
        if msg.get("emergency") and role == "assistant":
            st.error(msg["content"], icon="🚨")
        else:
            st.markdown(msg["content"])

        for path in msg.get("images", []):
            if Path(path).exists():  # small illustration on the left, caption beside it
                ci, ct = st.columns([1, 2.4])
                ci.image(path, width=230)
                ct.markdown('<div class="illus-cap">Generic educational illustration - '
                            'not a scan, result or diagnosis.</div>', unsafe_allow_html=True)

        if msg.get("audio"):
            autoplay = st.session_state.get("autoplay") == (chat["id"], i)
            try:
                st.audio(msg["audio"], format="audio/mp3", autoplay=autoplay)
            except TypeError:  # older Streamlit without autoplay
                st.audio(msg["audio"], format="audio/mp3")

        if role == "assistant" and not msg.get("welcome") and not msg.get("emergency"):
            c1, c2, c3, c4, _ = st.columns([1, 1.1, 0.85, 1.5, 2.2])
            base = f"{chat['id']}_{i}"
            if c1.button("Simplify", key=f"act_simp_{base}"):
                st.session_state.pending = ("Explain your previous answer again in very simple terms, "
                                            "as if to someone with no medical background.")
                st.rerun()
            if c2.button("Follow-up", key=f"act_fu_{base}"):
                st.session_state.pending = ("Suggest three follow-up questions I could ask a clinician "
                                            "about what we just discussed.")
                st.rerun()
            if c3.button("Listen", key=f"act_tts_{base}"):
                with st.spinner("Generating audio…"):
                    try:
                        msg["audio"] = run_in_worker(medora.synthesize_speech, msg["content"], voice=current_voice())
                        st.session_state.autoplay = (chat["id"], i)
                    except Exception as exc:
                        st.error(f"Text-to-speech failed: {exc}")
                st.rerun()
            if c4.button("Add to summary", key=f"act_sum_{base}"):
                snippet = msg["content"].strip().replace("\n", " ")
                chat["summary"].append(snippet[:160] + ("…" if len(snippet) > 160 else ""))
                st.toast("Added to visit summary.", icon="📋")
                st.rerun()


def chip(text: str, kind: str) -> str:
    return f'<span class="chip {kind}">{esc(text)}</span>'


def render_insights() -> None:
    n_files = len(chat["files"])
    recent_emergency = any(m.get("emergency") for m in chat["messages"][-3:])
    if recent_emergency:
        next_cls, next_txt = "alert", "Contact your local emergency number now."
    elif not n_files:
        next_cls, next_txt = "", "Upload a de-identified report to get a plain-language walkthrough."
    else:
        next_cls, next_txt = "", f"Ask about a value in {chat['files'][-1]['name']}."
    kb_on = bool(medora.KNOWLEDGE_BASE_VECTOR_STORE_ID)
    skill_on = bool(medora.SKILL_ID and medora.SKILL_MODEL)

    h('<div class="ins-title">Insights</div>')
    h(f'<div class="ins-next {next_cls}"><div class="k">Next step</div><div class="v">{esc(next_txt)}</div></div>')
    h('<div class="ins-h">Care team</div>')
    h("""
        <div class="ins-row"><span>Coordinator</span><span class="chip on">Routes</span></div>
        <div class="ins-row"><span>Medical Information</span><span class="chip on">Ready</span></div>
        <div class="ins-row"><span>Report Analysis</span><span class="chip on">Ready</span></div>
        <div class="ins-row"><span>Wellness</span><span class="chip on">Ready</span></div>
    """)
    h('<div class="ins-h">Tools</div>')
    h(f"""
        <div class="ins-row"><span>Web search</span>{chip("On", "on")}</div>
        <div class="ins-row"><span>Knowledge base</span>{chip("On", "on") if kb_on else chip("Not set", "off")}</div>
        <div class="ins-row"><span>Report search</span>{chip(f"{n_files} file{'s' if n_files != 1 else ''}", "on") if n_files else chip("No documents", "off")}</div>
        <div class="ins-row"><span>Evidence skill</span>{chip("On", "on") if skill_on else chip("Not set", "off")}</div>
        <div class="ins-row"><span>Image generation</span>{chip("On", "on")}</div>
        <div class="ins-row"><span>Voice in / out</span>{chip("On", "on")}</div>
    """)
    h('<div class="ins-h">Safety layers</div>')
    h("""
        <div class="ins-row"><span>Emergency screen</span><span class="chip on">Active</span></div>
        <div class="ins-row"><span>Input guardrail</span><span class="chip on">Active</span></div>
        <div class="ins-row"><span>Output guardrail</span><span class="chip on">Active</span></div>
    """)
    if chat["summary"]:
        h('<div class="ins-h">Visit summary</div>')
        for item in chat["summary"][-5:]:
            st.markdown(f"- {item}")
    h('<div class="fine">In an emergency, contact your local emergency number. '
      f'{esc(medora.DISCLAIMER)}</div>')


def handle_text_turn(prompt: str) -> None:
    emergency = medora.looks_like_emergency(prompt)
    with bx("ma_pending"):
        with st.spinner("Medora is thinking…"):
            medora.LAST_AGENT_NAME = None
            reply = run_in_worker(medora.handle_user_message, prompt, chat["id"], chat["vs_id"])
            reply, images = extract_images(reply)
            agent = agent_label(getattr(medora, "LAST_AGENT_NAME", None), images, emergency)
            audio = None
            if st.session_state.read_aloud:
                try:
                    audio = run_in_worker(medora.synthesize_speech, reply, voice=current_voice())
                except Exception:
                    # Text answer remains available even if speech synthesis fails.
                    st.toast("Could not create spoken audio for this reply. The text answer is still available.", icon="⚠️")
    chat["messages"].append(make_message("assistant", reply, images=images, audio=audio,
                                         emergency=emergency, agent=agent))
    if audio:
        st.session_state.autoplay = (chat["id"], len(chat["messages"]) - 1)
    auth.save_chat(UID, chat)


def handle_voice_turn(audio_bytes: bytes, filename: str, content_type: str) -> None:
    with bx("ma_pending"):
        with st.spinner("Listening, thinking and preparing a spoken reply…"):
            try:
                medora.LAST_AGENT_NAME = None
                result = run_in_worker(
                    medora.process_voice_message, audio_bytes=audio_bytes, session_id=chat["id"],
                    filename=filename, content_type=content_type, language=current_lang(),
                    uploaded_vector_store_id=chat["vs_id"], voice=current_voice())
            except Exception:
                st.session_state.flash = (
                    "Voice processing failed. Please try recording again or type your message. "
                    "If the problem continues, check the app server logs."
                )
                return
    transcript = result.get("transcript", "").strip()
    if not transcript:
        st.session_state.flash = "No speech was detected. Please record a clearer message or type your question."
        return
    reply, images = extract_images(result.get("response_text", "Sorry, I could not generate a response."))
    emergency = medora.looks_like_emergency(transcript)
    if chat["title"] == "New chat":
        chat["title"] = transcript[:40]
    chat["messages"].append(make_message("user", f"🎙️ {transcript}"))
    chat["messages"].append(make_message(
        "assistant", reply, images=images, audio=result.get("audio_bytes"), emergency=emergency,
        agent=agent_label(getattr(medora, "LAST_AGENT_NAME", None), images, emergency)))
    if result.get("audio_bytes"):
        st.session_state.autoplay = (chat["id"], len(chat["messages"]) - 1)
    auth.save_chat(UID, chat)


def render_chat() -> None:
    h(f"""
        <div class="topbar"><div>
          <div class="page-title">{esc(greeting(user['name']))}</div>
          <div class="page-sub">Educational health information, not medical advice</div>
        </div><div class="pills">
          <span class="pill">Model {esc(medora.MODEL.upper())}</span><span class="pill">Guardrails active</span>
        </div></div>
    """)

    try:  # scrolling area; CSS makes its height follow the window
        msgs = st.container(height=540, border=False, key="msgs")
    except TypeError:
        msgs = st.container(height=540, border=False)

    suggestion = None
    submitted = False
    typed, attached, voice_file = "", [], None

    with bx("dock"):
        # ---- pill row: Explain my report · Sleep tips · Draw the heart · Read replies aloud · Export chat
        with bx("chips"):
            cols = st.columns([1.2, 0.85, 1.05, 1.6, 1.0, 1.6])
            report_prompt = ("Explain my uploaded report in plain language." if chat["files"]
                             else "How can I get a lab report explained here?")
            for col, (label, text) in zip(cols[:3], [
                ("Explain my report", report_prompt),
                ("Sleep tips", "What are some evidence-informed tips for better sleep?"),
                ("Draw the heart", "Create a simple educational illustration of how the human heart works."),
            ]):
                if col.button(label, key=f"sug_{label}", use_container_width=True):
                    suggestion = text
            if cols[3].button(f"Read replies aloud: {'on' if st.session_state.read_aloud else 'off'}",
                              key="ra_btn", use_container_width=True):
                st.session_state.read_aloud = not st.session_state.read_aloud
                st.rerun()
            cols[4].download_button("Export chat", data=transcript_text(chat), file_name=f"medora_{chat['id']}.txt",
                                    mime="text/plain", use_container_width=True)

        # ---- composer: [ message ........ ][Attach report][Voice message][Send]
        # One form, so Enter or Send submits everything together: the typed text,
        # any report attached in the first popover, and any recording made in the second.
        with bx("composer"):
            with st.form("composer_form", clear_on_submit=True):
                c_txt, c_att, c_voi, c_send = st.columns([6, 1.5, 1.6, 0.9])
                typed = c_txt.text_input("Message", key="composer_text", label_visibility="collapsed",
                                         placeholder="Ask Medora about a health topic or your report…")
                with c_att.popover("Attach report", use_container_width=True):
                    attached = st.file_uploader("Attach a de-identified report", type=UPLOAD_TYPES,
                                                accept_multiple_files=True, key="composer_files")
                    st.caption("Then press Send. Medora indexes the file and can answer questions about it.")
                with c_voi.popover("Voice message", use_container_width=True):
                    if hasattr(st, "audio_input"):
                        voice_file = st.audio_input("Record a message", key="composer_voice")
                    else:
                        voice_file = st.file_uploader("Upload a voice recording",
                                                      type=["wav", "mp3", "m4a", "webm"], key="composer_voice")
                    st.caption("1) Click the microphone and speak  2) Click stop  3) Press Send. "
                               "Medora transcribes your speech, answers, and speaks the reply.")
                submitted = c_send.form_submit_button("Send", type="primary", use_container_width=True)

    # ---- work out what the user asked for this run
    new_text, do_voice = None, False
    if submitted:
        text = (typed or "").strip()
        files = list(attached or [])

        # Index new attachments. A return value of 0 can also mean the file was
        # already indexed, so do not use `indexed` as the only upload check.
        if files:
            index_files(chat, files)

        indexing_error = st.session_state.pop("flash", None)
        if indexing_error:
            st.error(indexing_error)
        elif voice_file is not None:
            do_voice = True
        elif text:
            new_text = text
        elif files and chat.get("files") and chat.get("vs_id"):
            filenames = ", ".join(f.name for f in files)
            new_text = (
                f"Please analyze the uploaded medical report file(s): {filenames}. "
                "Search the uploaded document collection using File Search. Explain "
                "the documented diagnosis, impression, findings, and relevant values "
                "in plain language. Clearly distinguish what the report states from "
                "general context, and do not infer or invent missing information."
            )

    new_text = new_text or suggestion or (None if do_voice else st.session_state.pop("pending", None))

    with msgs:
        for i, msg in enumerate(chat["messages"]):
            render_message(i, msg)
        st.session_state.pop("autoplay", None)  # play once, not on every rerun

        if new_text:
            if chat["title"] == "New chat":
                chat["title"] = new_text[:40]
            user_msg = make_message("user", new_text)
            chat["messages"].append(user_msg)
            render_message(len(chat["messages"]) - 1, user_msg)
            handle_text_turn(new_text)
            st.rerun()
        elif do_voice:
            data = voice_file.getvalue()
            ctype = getattr(voice_file, "type", None) or "audio/wav"
            fname = getattr(voice_file, "name", None) or "recording.wav"
            if "." not in fname:
                fname += ".wav"
            handle_voice_turn(data, fname, ctype)
            st.rerun()

    with bx("insights"):
        render_insights()

    try:  # keep the newest message in view
        components.html(
            "<script>setTimeout(function(){try{const m=window.parent.document"
            ".querySelectorAll('[class*=\"st-key-ma_\"],[class*=\"st-key-mu_\"]');"
            "if(m.length){m[m.length-1].scrollIntoView({block:'end'});}}catch(e){}},250);"
            "</script>", height=0)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
if page == "chat":  # room for the fixed Insights column on the right
    st.markdown("<style>.block-container{padding-right:336px !important;padding-bottom:16px !important}</style>",
                unsafe_allow_html=True)

if page == "history":
    render_history()
elif page == "documents":
    render_documents()
else:
    render_chat()

auth.save_chat(UID, chat)  # persist title / documents / summary changes