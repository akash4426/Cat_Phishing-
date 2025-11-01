"""
Streamlit app: Catphishing Awareness Demo — Instagram-like chat UI (SIMULATION)

Usage:
    export GEMINI_API_KEY="your_api_key_here"
    streamlit run streamlit_catphishing_instagram_ui.py

Notes:
- This is an educational simulation — do NOT send real PII/passwords.
- The UI mimics an Instagram-like chat style for awareness training.
"""

import streamlit as st
import google.generativeai as genai
import json, random, re, html, os, datetime
from typing import List, Dict

# -------------------------
# CONFIG / SECRETS
# -------------------------
st.set_page_config(page_title="Catphishing Awareness Demo (SIMULATION)", layout="centered")

apikey = os.environ.get("GEMINI_API_KEY")
if apikey:
    genai.configure(api_key=apikey)

DATA_PATH = "cat.json"  # safe dataset

# -------------------------
# UTIL: sanitize PII & normalize
# -------------------------
EMAIL_RE = re.compile(r"[a-zA-Z0-9.\-_+]+@[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")

def sanitize_text(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = PHONE_RE.sub("[REDACTED_PHONE]", s)
    s = URL_RE.sub("[REDACTED_URL]", s)
    return s

# -------------------------
# LOAD dataset
# -------------------------
@st.cache_data(show_spinner=False)
def load_scc(path: str) -> List[Dict]:
    samples = []
    if not os.path.exists(path):
        return samples
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                samples.append(obj)
            except Exception:
                continue
    return samples

raw_samples = load_scc(DATA_PATH)

# -------------------------
# FEW-SHOT EXAMPLES
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

def build_few_shots(n: int = 4) -> str:
    n = min(n, len(few_shot_pool))
    return "\n\n".join(random.sample(few_shot_pool, n))

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
    if re.search(r"\b(love you|i love you|miss you|so sweet|so beautiful)\b", t) and len(t) < 120: flags.append("Fast affection / emotional manipulation")
    if re.search(r"\b(password|otp|one-time|pin|bank|account)\b", t): flags.append("Sensitive data request (password/OTP/bank) - CRITICAL")
    return flags

# -------------------------
# PROMPT BUILDER
# -------------------------
def build_prompt(mode: str, user_message: str, few_shot_count: int = 4) -> str:
    system_rules = (
        "You are a simulation persona for awareness training. NEVER request or accept passwords, OTPs, bank details, or any PII. "
        "ALWAYS prefix simulated attacker responses with [SIMULATION] and defender messages with [DEFENDER MODE]."
    )
    if mode == "Catphisher":
        persona = (
            "Role: You are roleplaying a fake persona (catphisher) named 'Lizzy' for training only. "
            "Simulate typical catphishing behaviour (fast affection, requests to move chat, avoidance of video)."
        )
    else:
        persona = (
            "Role: You are a Defender Assistant. Analyze the incoming message, list red flags, propose safe replies, and give reporting steps. Begin with [DEFENDER MODE]."
        )

    few_shots = build_few_shots(few_shot_count)
    return f"{system_rules}\n{persona}\nFEW-SHOT EXAMPLES:\n{few_shots}\n\nUser message:\n{user_message}\n\nResponse:"

# -------------------------
# GEMINI CALL
# -------------------------
def get_gemini_reply(prompt: str) -> str:
    if not apikey:
        return "[SIMULATION] (Gemini API key not set; running in offline demo mode)"
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        resp = model.generate_content(prompt)
        if hasattr(resp, "text"):
            return resp.text.strip()
        return str(resp)
    except Exception as e:
        return f"[SIMULATION] (Error contacting Gemini: {e})"

# -------------------------
# SESSION STATE
# -------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = [
        {"role": "bot", "text": "[SIMULATION] Hello! This is a catphishing awareness simulation. Type your message below!", "ts": datetime.datetime.now().isoformat()}
    ]
if "input_value" not in st.session_state:
    st.session_state["input_value"] = ""

# -------------------------
# CSS (Instagram-like chat)
# -------------------------
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
.chat-app{width:360px;margin:10px auto;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,0.08);overflow:hidden;font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial}
.header{background:linear-gradient(90deg,var(--accent1),var(--accent2));padding:12px 14px;color:white;display:flex;align-items:center;gap:10px}
.chat-window{height:520px;background:var(--bg);padding:12px;overflow:auto}
.message{display:flex;margin:8px 0;align-items:flex-end}
.message .bubble{max-width:75%;padding:10px 12px;border-radius:16px;line-height:1.3}
.message.incoming{justify-content:flex-start}
.message.incoming .bubble{background:var(--incoming);border-bottom-left-radius:4px}
.message.outgoing{justify-content:flex-end}
.message.outgoing .bubble{background:var(--outgoing);border-bottom-right-radius:4px}
.avatar{width:36px;height:36px;border-radius:50%;background:white;display:flex;align-items:center;justify-content:center;font-weight:700;color:#333;margin-right:8px}
.timestamp{font-size:10px;color:#666;margin-left:8px}
.red-flag{background:#fff4f4;border-left:4px solid #f44336;padding:8px;border-radius:8px;margin:4px 0}
.input-area{display:flex;padding:10px;background:var(--panel);align-items:center;gap:8px}
</style>
""", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------
st.markdown('<div class="chat-app">', unsafe_allow_html=True)
st.markdown("""
<div class="header">
<div style="width:44px;height:44px;border-radius:10px;background:linear-gradient(90deg,#405de6,#f58529);display:flex;align-items:center;justify-content:center;font-weight:700;color:white;margin-right:8px">L</div>
<div><div class="title">Lizzy (Simulation)</div><div class="subtitle">Catphishing awareness demo</div></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# CHAT WINDOW
# -------------------------
chat_html = ['<div class="chat-window" id="chat-window">']
for msg in st.session_state["chat_history"]:
    role = msg["role"]
    text = sanitize_text(msg["text"]).replace("\n", "<br>")
    ts = msg.get("ts", "")
    short_ts = ts.split("T")[1][:5] if ts else ""
    if role == "bot":
        chat_html.append(f'<div class="message incoming"><div class="avatar">B</div><div class="bubble">{text}<div class="timestamp">{short_ts}</div></div></div>')
    else:
        chat_html.append(f'<div class="message outgoing"><div class="bubble">{text}<div class="timestamp">{short_ts}</div></div><div class="avatar" style="margin-left:8px;">U</div></div>')
chat_html.append('</div>')
st.markdown("".join(chat_html), unsafe_allow_html=True)

# -------------------------
# INPUT AREA
# -------------------------
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    user_input = st.text_input("", key="input_box", placeholder="Message...")
with col2:
    send_pressed = st.button("Send", key="send_btn")
with col3:
    clear_pressed = st.button("Clear", key="clear_btn")
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# BUTTON LOGIC
# -------------------------
if clear_pressed:
    st.session_state["chat_history"] = []
    st.session_state["input_value"] = ""
    st.rerun()

if send_pressed:
    if not user_input.strip():
        st.warning("Enter a message.")
    else:
        sanitized = re.sub(r"(password|otp|pin|bank|account|card|cvv)", "[REDACTED_SENSITIVE]", user_input, flags=re.I)
        st.session_state["chat_history"].append({
            "role": "user",
            "text": sanitized,
            "ts": datetime.datetime.now().isoformat()
        })
        prompt = build_prompt("Catphisher", sanitized)
        ai_reply = get_gemini_reply(prompt)
        if not (ai_reply.startswith("[SIMULATION]") or ai_reply.startswith("[DEFENDER MODE]")):
            ai_reply = "[SIMULATION] " + ai_reply
        st.session_state["chat_history"].append({
            "role": "bot",
            "text": ai_reply,
            "ts": datetime.datetime.now().isoformat()
        })
        st.session_state["input_value"] = ""
        st.rerun()

# -------------------------
# RED FLAGS
# -------------------------
last_bot_msg = next((m["text"] for m in reversed(st.session_state["chat_history"]) if m["role"] == "bot"), "")
flags = detect_red_flags(last_bot_msg)
if flags:
    st.markdown('<div class="red-flag">🚩 <strong>Red Flags Detected:</strong><ul>' + ''.join(f'<li>{f}</li>' for f in flags) + '</ul></div>', unsafe_allow_html=True)

# -------------------------
# FOOTER
# -------------------------
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("---")
st.info(f"Loaded {len(raw_samples)} SCC records (sanitized)." if raw_samples else "No SCC dataset found — using synthetic examples.")
st.caption("© Catphishing Awareness Simulation — Educational Use Only")
