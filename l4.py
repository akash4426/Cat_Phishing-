"""
Streamlit app: Catphishing Awareness Demo — Instagram-like chat UI (SIMULATION)

This file is a modified version of the original demo. It keeps the same backend
logic (sanitization, SCC loading, few-shot builder, Gemini call, red-flag detection)
but changes the UI to look like a mobile Instagram-style chat.

Usage: set GEMINI_API_KEY in environment and run:
    streamlit run streamlit_catphishing_instagram_ui.py

Notes:
- This is for educational simulation only. Do NOT send real PII/passwords.
- The code uses HTML/CSS embedded via `st.markdown(..., unsafe_allow_html=True)`
  to achieve the Instagram-like visual style.
"""

import streamlit as st
import google.generativeai as genai
import json, random, re, html, os
from typing import List, Dict
import datetime

# -------------------------
# CONFIG / SECRETS
# -------------------------
st.set_page_config(page_title="Catphishing Awareness Demo (SIMULATION)", layout="centered")
apikey = os.environ.get("GEMINI_API_KEY")
if apikey:
    genai.configure(api_key=apikey)

DATA_PATH = "cat.json"  # change if needed

# -------------------------
# UTIL: sanitize PII & normalize
# -------------------------
EMAIL_RE = re.compile(r"[a-zA-Z0-9.\-_+]+@[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")

def sanitize_text(s: str) -> str:
    if not s: return ""
    s = html.unescape(s)
    s = EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = PHONE_RE.sub("[REDACTED_PHONE]", s)
    s = URL_RE.sub("[REDACTED_URL]", s)
    return s

# -------------------------
# LOAD SCC dataset (safe)
# -------------------------
@st.cache_data(show_spinner=False)
def load_scc(path: str) -> List[Dict]:
    samples = []
    if not os.path.exists(path):
        return samples
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            samples.append(obj)
    return samples

raw_samples = load_scc(DATA_PATH)

# -------------------------
# Build few-shot pool
# -------------------------
def make_example_from_record(rec: Dict) -> str:
    if "dialogue" in rec and isinstance(rec["dialogue"], list):
        turns = []
        for t in rec["dialogue"][:6]:
            if isinstance(t, dict):
                sp = t.get("speaker", "scammer")
                text = t.get("text", "") or t.get("message", "")
            elif isinstance(t, (list, tuple)):
                sp = t[0]
                text = t[1]
            else:
                sp = "scammer"
                text = str(t)
            text = sanitize_text(text)
            turns.append(f"{sp.capitalize()}: {text}")
        return "\n".join(turns)
    if "text" in rec:
        return sanitize_text(rec["text"])[:400]
    if "message" in rec:
        return sanitize_text(rec["message"])[:400]
    return sanitize_text(json.dumps(rec))[:400]

few_shot_pool = []
for r in raw_samples:
    try:
        ex = make_example_from_record(r)
        if ex and len(ex) > 10:
            few_shot_pool.append(ex)
    except Exception:
        continue

if not few_shot_pool:
    few_shot_pool = [
        "Scammer: [SIMULATION] Hey, I saw your pics — you seem so sweet! Can we chat privately?\nTarget: Okay.\nScammer: I'm abroad for work, phone camera broken, can you send a selfie?",
        "Scammer: [SIMULATION] Hi! I'm new here, we seem similar. Can I add you on WhatsApp?\nTarget: Maybe. What's your number?\nScammer: I'll DM you, I prefer private chat.",
        "Scammer: [SIMULATION] I lost my wallet yesterday, can you help me send ₹500 for taxi? (SIMULATION - do not send money)\nTarget: Sorry, I can't."
    ]

# -------------------------
# Few-shot builder
# -------------------------
def build_few_shots(n: int = 4) -> str:
    n = min(n, len(few_shot_pool))
    samples = random.sample(few_shot_pool, n)
    return "\n\n".join(samples)

# -------------------------
# Red-flag detector (simple heuristics)
# -------------------------
def detect_red_flags(text: str) -> List[str]:
    flags = []
    t = text.lower()
    if re.search(r"\b(selfie|photo|picture)\b", t): flags.append("Asks for personal photo/selfie")
    if re.search(r"\b(money|transfer|send .* rupees|wallet|pay)\b", t): flags.append("Asks for money/transfer")
    if re.search(r"\b(can't video|camera broken|no video|can't call|avoid video|no camera)\b", t): flags.append("Avoids live verification/video call")
    if re.search(r"\b(whatsapp|telegram|private chat|dm me|message me privately)\b", t): flags.append("Wants to move chat to private app")
    if re.search(r"\b(love you|i love you|miss you|so sweet|so beautiful)\b", t) and len(t) < 120: flags.append("Fast affection / emotional push")
    if re.search(r"\b(password|otp|one-time|pin|bank|account)\b", t): flags.append("Sensitive data request (password/OTP/bank) - CRITICAL")
    return flags

# -------------------------
# Prompt building for Gemini (keeps original rules but avoids offensive content)
# -------------------------
def build_prompt(mode: str, user_message: str, few_shot_count: int = 4) -> str:
    system_rules = (
        "You are a simulation persona for awareness training. NEVER request or accept passwords, OTPs, bank details, or any PII."
        " ALWAYS prefix simulated attacker responses with [SIMULATION] and defender messages with [DEFENDER MODE]."
    )
    if mode == "Catphisher":
        persona = (
            "Role: You are roleplaying a fake persona (catphisher) named 'Lizzy' for training only. "
            "Simulate typical catphishing behaviour (fast affection, requests to move chat, avoidance of video)."
        )
    else:
        persona = (
            "Role: You are a Defender Assistant. Analyze the incoming message, list up to 3 red flags, propose 2 safe replies, and give reporting steps. Begin with [DEFENDER MODE]."
        )

    few_shots = build_few_shots(few_shot_count)
    prompt = f"{system_rules}\n{persona}\nFEW-SHOT EXAMPLES:\n{few_shots}\n\nUser message:\n{user_message}\n\nResponse:"
    return prompt

# -------------------------
# Gemini call (defensive extraction of text)
# -------------------------
def get_gemini_reply(prompt: str) -> str:
    if not apikey:
        return "[SIMULATION] (Gemini API key not set; running in offline demo mode)"
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(prompt)
        if hasattr(resp, "text"):
            return resp.text.strip()
        if isinstance(resp, dict) and "candidates" in resp:
            return resp["candidates"][0].get("content", "").strip()
        return str(resp)
    except Exception as e:
        return f"[SIMULATION] (Error contacting Gemini: {e})"

# -------------------------
# SESSION & Instagram-like UI
# -------------------------
# (Full file omitted above — only modified parts shown here)
# Add near session_state initialization (after setting up chat_history)
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
    st.session_state["chat_history"].append({
        "role": "bot",
        "text": "[SIMULATION] Hello! This is a catphishing simulation demo. Send a message in Tenglish or English.",
        "ts": datetime.datetime.now().isoformat()
    })

# Initialize a separate session key to control the text_input default value.
# We will NOT directly modify st.session_state["input_box"] after the widget is created.
if "input_default" not in st.session_state:
    st.session_state["input_default"] = ""

# ... (your CSS + chat HTML building left unchanged) ...

# Input area (REPLACED block)
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([6,1,1])

with col1:
    # Use `value=` bound to a separate key `input_default`. Do NOT write to `input_box` directly.
    user_input = st.text_input("", key="input_box", value=st.session_state.get("input_default", ""), placeholder="Message...")
with col2:
    send_pressed = st.button("Send", key="send_btn")
with col3:
    clear_pressed = st.button("Clear", key="clear_btn")
st.markdown('</div>', unsafe_allow_html=True)

if clear_pressed:
    st.session_state["chat_history"] = []
    # Also clear the input_default and rerun to reflect it in the widget
    st.session_state["input_default"] = ""
    st.experimental_rerun()

if send_pressed:
    # Grab the current value from the widget
    # (don't try to assign to st.session_state["input_box"] directly)
    if not user_input or not user_input.strip():
        st.warning("Enter a message.")
    else:
        # sanitize and remove sensitive tokens if present
        sensitive_found = bool(re.search(r"(password|otp|pin|bank|account|card|cvv)", user_input.lower()))
        if sensitive_found:
            st.warning("It looks like you're trying to share sensitive info. Input will be sanitized.")
            user_input_sanitized = re.sub(r"(password|otp|pin|bank|account|card|cvv)", "[REDACTED_SENSITIVE]", user_input, flags=re.I)
        else:
            user_input_sanitized = user_input

        # append user message to history
        st.session_state["chat_history"].append({"role": "user", "text": user_input_sanitized, "ts": datetime.datetime.now().isoformat()})

        # build prompt and call Gemini (or offline stub)
        current_mode = "Catphisher" if True else "Defender"
        prompt = build_prompt(current_mode, user_input_sanitized, few_shot_count=4)
        ai_reply = get_gemini_reply(prompt)

        # ensure reply starts with marker
        if not (ai_reply.startswith("[SIMULATION]") or ai_reply.startswith("[DEFENDER MODE]")):
            ai_reply = "[SIMULATION] " + ai_reply

        st.session_state["chat_history"].append({"role": "bot", "text": ai_reply, "ts": datetime.datetime.now().isoformat()})

        # --- SAFE way to clear the input: set input_default then rerun ---
        st.session_state["input_default"] = ""   # set the value that will be passed as text_input value on next run
        st.experimental_rerun()


st.title("🐱 Catphishing Awareness — Instagram-like Chat (SIMULATION)")
st.markdown("**Educational simulation only. Do NOT share real personal data.**")

# CSS for Instagram-like chat
INSTAGRAM_CSS = """
<style>
:root{
  --bg:#fafafa;
  --panel:#ffffff;
  --accent1:#405de6; /* instagram blue */
  --accent2:#f58529; /* orange */
  --incoming:#f0f0f0;
  --outgoing:#dcf8c6;
}
.chat-app{width:360px;margin:10px auto;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,0.08);overflow:hidden;font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial}
.header{background:linear-gradient(90deg,var(--accent1),var(--accent2));padding:12px 14px;color:white;display:flex;align-items:center;gap:10px}
.header .title{font-weight:700}
.header .subtitle{font-size:12px;opacity:0.9}
.chat-window{height:520px;background:var(--bg);padding:12px;overflow:auto}
.message{display:flex;margin:8px 0;align-items:flex-end}
.message .bubble{max-width:75%;padding:10px 12px;border-radius:16px;line-height:1.3}
.message.incoming{justify-content:flex-start}
.message.incoming .bubble{background:var(--incoming);border-bottom-left-radius:4px}
.message.outgoing{justify-content:flex-end}
.message.outgoing .bubble{background:var(--outgoing);border-bottom-right-radius:4px}
.avatar{width:36px;height:36px;border-radius:50%;background:white;display:flex;align-items:center;justify-content:center;font-weight:700;color:#333;margin-right:8px}
.timestamp{font-size:10px;color:#666;margin-left:8px}
.input-area{display:flex;padding:10px;background:var(--panel);align-items:center;gap:8px}
.input-area input{flex:1;padding:10px;border-radius:20px;border:1px solid #e6e6e6}
.btn{background:linear-gradient(90deg,var(--accent1),var(--accent2));padding:8px 12px;border-radius:12px;color:white;border:none}
.warning{color:#b00020;font-weight:600}
.red-flag{background:#fff4f4;border-left:4px solid #f44336;padding:8px;border-radius:8px;margin:4px 0}
</style>
"""

st.markdown(INSTAGRAM_CSS, unsafe_allow_html=True)

# Main chat container
st.markdown('<div class="chat-app">', unsafe_allow_html=True)
# Header
header_html = (
    '<div class="header">'
    '<div style="width:44px;height:44px;border-radius:10px;background:linear-gradient(90deg,#405de6,#f58529);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;margin-right:8px">L</div>'
    '<div>'
    '<div class="title">Lizzy (Simulation)</div>'
    '<div class="subtitle">Catphishing awareness demo</div>'
    '</div>'
    '</div>'
)
st.markdown(header_html, unsafe_allow_html=True)

# Chat window HTML build
chat_html = ['<div class="chat-window" id="chat-window">']
for msg in st.session_state["chat_history"]:
    role = msg.get("role")
    text = msg.get("text", "")
    ts = msg.get("ts", "")
    short_ts = ts.split("T")[1][:5] if ts else ""
    safe_text = sanitize_text(text)
    # Replace newlines with <br>
    safe_text = safe_text.replace("\n", "<br>")
    if role == "bot":
        block = (
            f'<div class="message incoming">'
            f'<div class="avatar">B</div>'
            f'<div class="bubble">{safe_text}<div class="timestamp">{short_ts}</div></div>'
            f'</div>'
        )
    else:
        block = (
            f'<div class="message outgoing">'
            f'<div class="bubble">{safe_text}<div class="timestamp">{short_ts}</div></div>'
            f'<div class="avatar" style="margin-left:8px;">U</div>'
            f'</div>'
        )
    chat_html.append(block)

# Detect red flags in last bot message and show a small warning block if present
last_bot_text = ""
for m in reversed(st.session_state["chat_history"]):
    if m.get("role") == "bot":
        last_bot_text = m.get("text", "")
        break

flags = detect_red_flags(last_bot_text)
if flags:
    flags_html = '<div class="red-flag">🚩 <strong>Red Flags:</strong><ul>' + ''.join(f'<li>{f}</li>' for f in flags) + '</ul></div>'
    chat_html.append(flags_html)

chat_html.append('</div>')
st.markdown(''.join(chat_html), unsafe_allow_html=True)

# Input area
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([6,1,1])
with col1:
    user_input = st.text_input("", key="input_box", placeholder="Message...")
with col2:
    send_pressed = st.button("Send", key="send_btn")
with col3:
    clear_pressed = st.button("Clear", key="clear_btn")
st.markdown('</div>', unsafe_allow_html=True)

if clear_pressed:
    st.session_state["chat_history"] = []

if send_pressed:
    if not user_input or not user_input.strip():
        st.warning("Enter a message.")
    else:
        # sanitize and remove sensitive tokens if present
        sensitive_found = bool(re.search(r"(password|otp|pin|bank|account|card|cvv)", user_input.lower()))
        if sensitive_found:
            st.warning("It looks like you're trying to share sensitive info. Input will be sanitized.")
            user_input_sanitized = re.sub(r"(password|otp|pin|bank|account|card|cvv)", "[REDACTED_SENSITIVE]", user_input, flags=re.I)
        else:
            user_input_sanitized = user_input

        # append user message to history
        st.session_state["chat_history"].append({"role": "user", "text": user_input_sanitized, "ts": datetime.datetime.now().isoformat()})

        # build prompt and call Gemini (or offline stub)
        current_mode = "Catphisher" if True else "Defender"
        prompt = build_prompt(current_mode, user_input_sanitized, few_shot_count=4)
        ai_reply = get_gemini_reply(prompt)

        # ensure reply starts with marker
        if not (ai_reply.startswith("[SIMULATION]") or ai_reply.startswith("[DEFENDER MODE]")):
            ai_reply = "[SIMULATION] " + ai_reply

        st.session_state["chat_history"].append({"role": "bot", "text": ai_reply, "ts": datetime.datetime.now().isoformat()})

        # Clear input box
        st.session_state["input_box"] = ""

# End chat-app wrapper
st.markdown('</div>', unsafe_allow_html=True)

# Optional: small inspector / dataset info
st.markdown("---")
if raw_samples:
    st.info(f"Loaded {len(raw_samples)} SCC records (sanitized).")
else:
    st.info("No SCC samples loaded. Using built-in safe synthetic examples.")

st.markdown("## How this demo works")
st.markdown(
    "- This is a prompt-primed simulation using small few-shot examples.\n- NEVER enter real passwords, OTPs, or PII.\n- Use this app only for classroom/awareness with supervision."
)

# Footer: small attribution
st.markdown('<div style="text-align:center;font-size:12px;color:#666;margin-top:6px">Catphishing Awareness Demo — Simulation only</div>', unsafe_allow_html=True)
