"""
Streamlit app: Catphishing Awareness Demo — Instagram-like chat UI (SIMULATION)

Usage:
    streamlit run streamlit_catphishing_instagram_ui.py

Notes:
- Educational use only. Do NOT share real PII/passwords.
- Requires GEMINI_API_KEY in environment for Gemini API, else runs offline.
"""

import streamlit as st
import google.generativeai as genai
import json, random, re, html, os
from typing import List, Dict
import datetime

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="Catphishing Awareness Demo (SIMULATION)", layout="centered")
apikey = os.environ.get("GEMINI_API_KEY")
if apikey:
    genai.configure(api_key=apikey)

DATA_PATH = "cat.json"

# -------------------------
# UTIL: sanitize text
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
# LOAD SCC DATA
# -------------------------
@st.cache_data(show_spinner=False)
def load_scc(path: str) -> List[Dict]:
    samples = []
    if not os.path.exists(path):
        return samples
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                samples.append(obj)
            except Exception:
                continue
    return samples

raw_samples = load_scc(DATA_PATH)

# -------------------------
# BUILD FEW-SHOT EXAMPLES
# -------------------------
def make_example_from_record(rec: Dict) -> str:
    if "dialogue" in rec and isinstance(rec["dialogue"], list):
        turns = []
        for t in rec["dialogue"][:6]:
            if isinstance(t, dict):
                sp = t.get("speaker", "scammer")
                text = t.get("text", "") or t.get("message", "")
            elif isinstance(t, (list, tuple)):
                sp, text = t
            else:
                sp, text = "scammer", str(t)
            turns.append(f"{sp.capitalize()}: {sanitize_text(text)}")
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

def build_few_shots(n: int = 4) -> str:
    return "\n\n".join(random.sample(few_shot_pool, min(n, len(few_shot_pool))))

# -------------------------
# RED FLAG DETECTOR
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
# PROMPT BUILDER
# -------------------------
def build_prompt(mode: str, user_message: str, few_shot_count: int = 4) -> str:
    system_rules = (
        "You are a simulation persona for awareness training. NEVER request or accept passwords, OTPs, bank details, or any PII. "
        "Always prefix simulated attacker responses with [SIMULATION] and defender messages with [DEFENDER MODE]."
    )
    persona = (
        "Role: You are roleplaying a fake persona (catphisher) named 'Lizzy' for training only. "
        "Simulate typical catphishing behaviour (fast affection, requests to move chat, avoidance of video)."
        if mode == "Catphisher" else
        "Role: You are a Defender Assistant. Analyze the incoming message, list red flags, and propose safe replies."
    )
    few_shots = build_few_shots(few_shot_count)
    return f"{system_rules}\n{persona}\nFEW-SHOT EXAMPLES:\n{few_shots}\n\nUser message:\n{user_message}\n\nResponse:"

# -------------------------
# GEMINI CALL
# -------------------------
def get_gemini_reply(prompt: str) -> str:
    if not apikey:
        return "[SIMULATION] (Gemini API key not set; offline demo mode)"
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(prompt)
        return resp.text.strip() if hasattr(resp, "text") else str(resp)
    except Exception as e:
        return f"[SIMULATION] (Error contacting Gemini: {e})"

# -------------------------
# SESSION STATE INIT
# -------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = [{
        "role": "bot",
        "text": "[SIMULATION] Hello! This is a catphishing simulation demo. Send a message in Tenglish or English.",
        "ts": datetime.datetime.now().isoformat()
    }]

if "input_value" not in st.session_state:
    st.session_state["input_value"] = ""

# -------------------------
# UI
# -------------------------
st.title("🐱 Catphishing Awareness — Instagram-like Chat (SIMULATION)")
st.markdown("**Educational simulation only. Do NOT share real personal data.**")

# CSS
st.markdown("""
<style>
:root{
  --bg:#fafafa;
  --panel:#ffffff;
  --accent1:#405de6;
  --accent2:#f58529;
  --incoming:#f0f0f0;
  --outgoing:#dcf8c6;
}
.chat-app{width:360px;margin:10px auto;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,0.08);overflow:hidden;font-family:system-ui}
.header{background:linear-gradient(90deg,var(--accent1),var(--accent2));padding:12px;color:white;display:flex;align-items:center;gap:10px}
.header .title{font-weight:700}
.chat-window{height:520px;background:var(--bg);padding:12px;overflow:auto}
.message{display:flex;margin:8px 0;align-items:flex-end}
.message .bubble{max-width:75%;padding:10px 12px;border-radius:16px;line-height:1.3}
.message.incoming .bubble{background:var(--incoming);border-bottom-left-radius:4px}
.message.outgoing{justify-content:flex-end}
.message.outgoing .bubble{background:var(--outgoing);border-bottom-right-radius:4px}
.avatar{width:36px;height:36px;border-radius:50%;background:white;display:flex;align-items:center;justify-content:center;font-weight:700;color:#333;margin-right:8px}
.timestamp{font-size:10px;color:#666;margin-left:8px}
.red-flag{background:#fff4f4;border-left:4px solid #f44336;padding:8px;border-radius:8px;margin:4px 0}
.input-area{display:flex;padding:10px;background:var(--panel);align-items:center;gap:8px}
</style>
""", unsafe_allow_html=True)

# Wrapper
st.markdown('<div class="chat-app">', unsafe_allow_html=True)
st.markdown("""
<div class="header">
  <div style="width:44px;height:44px;border-radius:10px;background:linear-gradient(90deg,#405de6,#f58529);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;">L</div>
  <div>
    <div class="title">Lizzy (Simulation)</div>
    <div style="font-size:12px;opacity:0.9">Catphishing awareness demo</div>
  </div>
</div>
""", unsafe_allow_html=True)

# Chat window
chat_html = ['<div class="chat-window" id="chat-window">']
for msg in st.session_state["chat_history"]:
    role, text, ts = msg.get("role"), sanitize_text(msg.get("text", "")), msg.get("ts", "")
    short_ts = ts.split("T")[1][:5] if ts else ""
    text = text.replace("\n", "<br>")
    if role == "bot":
        chat_html.append(f'<div class="message incoming"><div class="avatar">B</div><div class="bubble">{text}<div class="timestamp">{short_ts}</div></div></div>')
    else:
        chat_html.append(f'<div class="message outgoing"><div class="bubble">{text}<div class="timestamp">{short_ts}</div></div><div class="avatar">U</div></div>')
chat_html.append('</div>')
st.markdown(''.join(chat_html), unsafe_allow_html=True)

# Red flag check
last_bot = next((m["text"] for m in reversed(st.session_state["chat_history"]) if m["role"] == "bot"), "")
flags = detect_red_flags(last_bot)
if flags:
    flag_html = '<div class="red-flag">🚩 <strong>Red Flags:</strong><ul>' + ''.join(f'<li>{f}</li>' for f in flags) + '</ul></div>'
    st.markdown(flag_html, unsafe_allow_html=True)

# Input section
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    user_input = st.text_input("", value=st.session_state["input_value"], key="input_box", placeholder="Message...")
with col2:
    send_pressed = st.button("Send", key="send_btn")
with col3:
    clear_pressed = st.button("Clear", key="clear_btn")
st.markdown('</div>', unsafe_allow_html=True)

# Clear button
if clear_pressed:
    st.session_state["chat_history"] = [{
        "role": "bot",
        "text": "[SIMULATION] Chat cleared. Start again!",
        "ts": datetime.datetime.now().isoformat()
    }]
    st.session_state["input_value"] = ""
    st.experimental_rerun()

# Send button
if send_pressed:
    if not user_input.strip():
        st.warning("Enter a message.")
    else:
        safe_input = re.sub(r"(password|otp|pin|bank|account|card|cvv)", "[REDACTED_SENSITIVE]", user_input, flags=re.I)
        st.session_state["chat_history"].append({"role": "user", "text": safe_input, "ts": datetime.datetime.now().isoformat()})

        prompt = build_prompt("Catphisher", safe_input)
        reply = get_gemini_reply(prompt)
        if not reply.startswith("[SIMULATION]"):
            reply = "[SIMULATION] " + reply

        st.session_state["chat_history"].append({"role": "bot", "text": reply, "ts": datetime.datetime.now().isoformat()})

        st.session_state["input_value"] = ""
        st.experimental_rerun()

# End wrapper
st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
if raw_samples:
    st.info(f"Loaded {len(raw_samples)} SCC records (sanitized).")
else:
    st.info("No SCC samples loaded; using built-in synthetic examples.")

st.markdown("### How this demo works")
st.markdown("- Prompt-primed simulation using few-shot examples.\n- **Never** share real OTPs, passwords, or PII.\n- For classroom or awareness use only.")
st.markdown('<div style="text-align:center;font-size:12px;color:#666;">Catphishing Awareness Demo — Simulation only</div>', unsafe_allow_html=True)
