"""
Streamlit app: Catphishing Awareness Demo — Instagram-like Chat UI (SIMULATION)

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
st.set_page_config(page_title="Catphishing Awareness (SIMULATION)", layout="centered")
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
        "Scammer: [SIMULATION] Hey, I saw your pics — you seem so sweet! Can we chat privately?\nTarget: Okay.\nScammer: I'm abroad for work, camera broken, can you send a selfie?",
        "Scammer: [SIMULATION] Hi! I'm new here, can I add you on WhatsApp?\nTarget: Maybe.\nScammer: I'll DM you privately.",
        "Scammer: [SIMULATION] I lost my wallet yesterday, can you send ₹500 for a taxi? (SIMULATION - don’t send money)\nTarget: Sorry, I can’t."
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
# SESSION INIT
# -------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = [{
        "role": "bot",
        "text": "[SIMULATION] Hello! Choose a mode and start chatting.",
        "ts": datetime.datetime.now().isoformat()
    }]
if "input_value" not in st.session_state:
    st.session_state["input_value"] = ""
if "mode" not in st.session_state:
    st.session_state["mode"] = "Catphisher"

# -------------------------
# DARK MODE UI
# -------------------------
st.markdown("""
<style>
body { background-color: #0E1117; color: #FAFAFA; }
.chat-app { width: 400px; margin: auto; border-radius: 14px; overflow: hidden; background-color: #1A1D23; box-shadow: 0 4px 20px rgba(255,255,255,0.1); }
.header { background: linear-gradient(90deg, #405de6, #f58529); padding: 12px; color: white; display: flex; align-items: center; gap: 10px; }
.chat-window { height: 480px; padding: 12px; overflow-y: auto; background: #0E1117; }
.message { display: flex; margin: 8px 0; align-items: flex-end; }
.message .bubble { max-width: 75%; padding: 10px 12px; border-radius: 16px; line-height: 1.3; word-wrap: break-word; }
.message.incoming .bubble { background: #262B36; border-bottom-left-radius: 4px; color: #FAFAFA; }
.message.outgoing { justify-content: flex-end; }
.message.outgoing .bubble { background: #0078FF; color: white; border-bottom-right-radius: 4px; }
.timestamp { font-size: 10px; color: #888; margin-top: 4px; }
.red-flag { background: #2C1A1A; border-left: 4px solid #f44336; padding: 8px; border-radius: 8px; margin: 6px 0; }
.input-area { display: flex; gap: 8px; background: #1A1D23; padding: 10px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------
st.markdown(f"""
<div class="chat-app">
  <div class="header">
    <div style="width:44px;height:44px;border-radius:10px;background:white;display:flex;align-items:center;justify-content:center;color:#000;font-weight:700;">L</div>
    <div>
      <div style="font-weight:700;">Lizzy (Simulation)</div>
      <div style="font-size:12px;">Mode: {st.session_state["mode"]}</div>
    </div>
  </div>
""", unsafe_allow_html=True)

# -------------------------
# CHAT DISPLAY
# -------------------------
chat_html = ['<div class="chat-window">']
for msg in st.session_state["chat_history"]:
    role, text, ts = msg.get("role"), sanitize_text(msg.get("text", "")), msg.get("ts", "")
    short_ts = ts.split("T")[1][:5] if ts else ""
    text = text.replace("\n", "<br>")
    if role == "bot":
        chat_html.append(f'<div class="message incoming"><div class="bubble">{text}<div class="timestamp">{short_ts}</div></div></div>')
    else:
        chat_html.append(f'<div class="message outgoing"><div class="bubble">{text}<div class="timestamp">{short_ts}</div></div></div>')
chat_html.append('</div>')
st.markdown(''.join(chat_html), unsafe_allow_html=True)

# -------------------------
# RED FLAG DETECTION
# -------------------------
last_bot = next((m["text"] for m in reversed(st.session_state["chat_history"]) if m["role"] == "bot"), "")
flags = detect_red_flags(last_bot)
if flags:
    st.markdown('<div class="red-flag">🚩 <b>Red Flags Detected:</b><ul>' + ''.join(f'<li>{f}</li>' for f in flags) + '</ul></div>', unsafe_allow_html=True)

# -------------------------
# INPUT + BUTTONS
# -------------------------
user_input = st.text_input("Type a message...", value=st.session_state["input_value"], key="input_box")
col1, col2, col3 = st.columns([2, 2, 2])
with col1:
    send_pressed = st.button("Send 💬", key="send_btn")
with col2:
    clear_pressed = st.button("Clear 🗑️", key="clear_btn")
with col3:
    toggle_mode = st.button("Switch Mode 🔁", key="toggle_btn")

# -------------------------
# BUTTON LOGIC
# -------------------------
if toggle_mode:
    st.session_state["mode"] = "Defender" if st.session_state["mode"] == "Catphisher" else "Catphisher"
    st.rerun()

if clear_pressed:
    st.session_state["chat_history"] = [{
        "role": "bot",
        "text": "[SIMULATION] Chat cleared. Start again!",
        "ts": datetime.datetime.now().isoformat()
    }]
    st.session_state["input_value"] = ""
    st.rerun()

if send_pressed:
    if not user_input.strip():
        st.warning("Enter a message.")
    else:
        safe_input = re.sub(r"(password|otp|pin|bank|account|card|cvv)", "[REDACTED_SENSITIVE]", user_input, flags=re.I)
        st.session_state["chat_history"].append({"role": "user", "text": safe_input, "ts": datetime.datetime.now().isoformat()})
        prompt = build_prompt(st.session_state["mode"], safe_input)
        reply = get_gemini_reply(prompt)
        if not reply.startswith("[SIMULATION]") and not reply.startswith("[DEFENDER MODE]"):
            reply = f"[{'DEFENDER MODE' if st.session_state['mode']=='Defender' else 'SIMULATION'}] " + reply
        st.session_state["chat_history"].append({"role": "bot", "text": reply, "ts": datetime.datetime.now().isoformat()})
        st.session_state["input_value"] = ""
        st.rerun()

# -------------------------
# FOOTER
# -------------------------
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("---")
st.info(f"Mode: {st.session_state['mode']} | Loaded {len(raw_samples)} SCC records")
st.caption("Catphishing Awareness Simulation — Educational Use Only © 2025")
