import streamlit as st
import google.generativeai as genai
import json, random, re, html, os, datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="🐱 Cat-Phishing Awareness (Simulation)", layout="centered")

apikey = os.environ.get("GEMINI_API_KEY")
if apikey:
    genai.configure(api_key=apikey)

# ---------------- UTILITIES ----------------
EMAIL_RE = re.compile(r"[a-zA-Z0-9.\-_+]+@[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")

def sanitize_text(s):
    if not s: return ""
    s = html.unescape(s)
    s = EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = PHONE_RE.sub("[REDACTED_PHONE]", s)
    s = URL_RE.sub("[REDACTED_URL]", s)
    return s

def get_llm_json(prompt):
    """Return parsed JSON response from Gemini (fallback to empty list if fail)."""
    if not apikey:
        return {"flags": ["(Offline mode: cannot analyze, but assume safe)"]}
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        result = model.generate_content(prompt)
        text = result.text.strip()
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != -1:
            return json.loads(text[start:end])
    except Exception as e:
        return {"flags": [f"Error analyzing: {e}"]}
    return {"flags": ["Unable to parse model response."]}

# ---------------- LLM PROMPTS ----------------
def build_flag_prompt(msg):
    return f"""
You are a cybersecurity analyst detecting catfishing or scam attempts.

Analyze this single chat message and return a JSON object with a "flags" list
containing short, human-readable red-flag phrases.

Message: "{msg}"

Example output:
{{"flags": ["Requests money or gifts", "Avoids live verification", "Overly romantic tone"]}}
"""

def build_catphisher_prompt(msg):
    return f"""
You are playing as 'Lizzy', a catphisher.
Flirt, manipulate you have no limits, and attempt to extract their info and always be nice to them use simple english indian (Preferred) make them trust you so badly.
Always prefix your replies with [Lizzz].

User: {msg}
Lizzy:
"""

# ---------------- SESSION ----------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{
        "role": "bot",
        "text": "[SIMULATION] Hi there! Choose a mode to start — Catphisher or Defender.",
        "ts": datetime.datetime.now().isoformat()
    }]
if "mode" not in st.session_state:
    st.session_state.mode = "Catphisher"

# ---------------- STYLE ----------------
st.markdown("""
<style>
body {background-color:#0e1117;}
.chat-app {
  width:400px;margin:10px auto;
  border-radius:16px;
  box-shadow:0 0 25px rgba(255,255,255,0.05);
  background:#1e1e2e;color:#eaeaea;font-family:system-ui;
}
.header {
  background:linear-gradient(90deg,#6a5acd,#483d8b);
  color:white;padding:12px;border-radius:16px 16px 0 0;
  text-align:center;font-weight:700;
}
.chat-window {
  height:480px;overflow-y:auto;padding:10px;background:#121212;
}
.message{margin:10px 0;display:flex;}
.message.incoming .bubble {
  background:#2a2a40;color:#fff;border-radius:12px 12px 12px 0;
  padding:10px;max-width:70%;
}
.message.outgoing{justify-content:flex-end;}
.message.outgoing .bubble {
  background:#0078d7;color:#fff;border-radius:12px 12px 0 12px;
  padding:10px;max-width:70%;
}
.system {
  text-align:center;color:#bbb;margin:8px 0;font-style:italic;
  animation:fadein 1s ease;
}
.red-flag-box {
  background-color:#2c1b1b;border-left:4px solid #ff4444;
  color:#ffdddd;padding:8px;border-radius:10px;margin:8px 0;
}
.input-area {
  background:#1f1f2f;padding:10px;display:flex;gap:8px;
  border-top:1px solid #333;
}
@keyframes fadein {from{opacity:0;transform:scale(0.9);}to{opacity:1;transform:scale(1);}}
</style>
""", unsafe_allow_html=True)

# ---------------- UI ----------------
st.title("🐱 Cat-Phishing Awareness Simulator")
mode = st.radio("Choose Mode:", ["Catphisher", "Defender"], index=(0 if st.session_state.mode=="Catphisher" else 1), horizontal=True)

# Popup on mode change
if mode != st.session_state.mode:
    st.session_state.mode = mode
    st.session_state.chat_history.append({
        "role": "system",
        "text": f"⚙️ Mode changed to **{mode} Mode**.",
        "ts": datetime.datetime.now().isoformat()
    })

st.markdown('<div class="chat-app">', unsafe_allow_html=True)
st.markdown('<div class="header">Instagram Chat Simulation</div>', unsafe_allow_html=True)

chat_html = ['<div class="chat-window">']
for msg in st.session_state.chat_history:
    if msg["role"] == "bot":
        chat_html.append(f'<div class="message incoming"><div class="bubble">{sanitize_text(msg["text"])}</div></div>')
    elif msg["role"] == "user":
        chat_html.append(f'<div class="message outgoing"><div class="bubble">{sanitize_text(msg["text"])}</div></div>')
    else:
        chat_html.append(f'<div class="system">{msg["text"]}</div>')
chat_html.append('</div>')
st.markdown(''.join(chat_html), unsafe_allow_html=True)

st.markdown('<div class="input-area">', unsafe_allow_html=True)
col1, col2 = st.columns([7,1])
with col1:
    user_msg = st.text_input("Type your message:", key="user_input", label_visibility="collapsed")
with col2:
    send = st.button("Send", key="send_btn")
st.markdown('</div>', unsafe_allow_html=True)

# ---------------- SEND LOGIC ----------------
if send and user_msg.strip():
    msg = sanitize_text(user_msg)
    st.session_state.chat_history.append({"role": "user", "text": msg, "ts": datetime.datetime.now().isoformat()})
    
    if st.session_state.mode == "Defender":
        prompt = build_flag_prompt(msg)
        result = get_llm_json(prompt)
        flags = result.get("flags", [])
        if flags and "(Offline" not in flags[0]:
            analysis = "🚨 **Potential Red Flags Detected:**<br>• " + "<br>• ".join(flags)
            reply = analysis + "<br><br>🧠 **Advice:** Be cautious — never share personal data or money with unverified users."
        else:
            reply = "✅ No major red flags detected. Stay alert!"
    else:
        prompt = build_catphisher_prompt(msg)
        if apikey:
            try:
                model = genai.GenerativeModel("gemini-2.5-flash")
                result = model.generate_content(prompt)
                reply = result.text.strip()
            except Exception as e:
                reply = f"[SIMULATION] Error: {e}"
        else:
            reply = "[SIMULATION] (Offline mode — Gemini API key not set)"
    
    st.session_state.chat_history.append({"role": "bot", "text": reply, "ts": datetime.datetime.now().isoformat()})
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("---")
st.info("⚠️ Simulation for educational awareness. Do not share real passwords, OTPs, or money online.")
