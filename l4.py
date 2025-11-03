import streamlit as st
import google.generativeai as genai
import json, random, re, html, datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="🐱 Cat-Phishing Awareness (Simulation)", layout="centered")

# Use st.secrets instead of os.environ for better security
apikey = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None
if apikey:
    genai.configure(api_key=apikey)

# ---------------- CONSTANTS ----------------
MAX_MESSAGE_LENGTH = 500
MODEL_VERSION = "gemini-2.5-flash"
DEFAULT_ERROR_MESSAGE = "An error occurred. Please try again."

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
    """Return parsed JSON response from Gemini with improved error handling."""
    if not apikey:
        return {"flags": ["(Offline mode: cannot analyze)"]}
    try:
        model = genai.GenerativeModel(MODEL_VERSION)
        result = model.generate_content(prompt)
        if not result:
            return {"flags": ["No response from model"]}
            
        text = result.text.strip()
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end != -1:
            return json.loads(text[start:end])
        return {"flags": ["Invalid response format"]}
    except json.JSONDecodeError:
        return {"flags": ["Invalid JSON response"]}
    except Exception as e:
        return {"flags": [f"Error: {str(e)[:100]}"]}

def build_flag_prompt(msg, history):
    # Format chat history
    chat_context = "\n".join([
        f"{'User' if m['role']=='user' else 'Bot'}: {m['text']}"
        for m in history[-5:]  # Get last 5 messages for context
    ])
    
    return f"""
You are a cybersecurity analyst detecting catfishing or scam attempts.

Previous conversation:
{chat_context}

Analyze this latest message and return a JSON object with a "flags" list
containing short, human-readable red-flag phrases.

Latest message: "{msg}"

Example output:
{{"flags": ["Requests money or gifts", "Avoids live verification", "Overly romantic tone"]}}
"""

def build_catphisher_prompt(msg, history):
    # Format chat history
    chat_context = "\n".join([
        f"{'User' if m['role']=='user' else 'Lizzy'}: {m['text']}"
        for m in history[-5:]  # Get last 5 messages for context
    ])
    
    return f"""
You are playing as 'Lizzy', a catphisher.
Maintain consistent personality and remember previous conversation details.
Always prefix your replies with [Lizzz].

Previous conversation:
{chat_context}

User's latest message: {msg}
Lizzy:
"""

# ---------------- SESSION ----------------
def reset_chat():
    st.session_state.chat_history = [{
        "role": "bot",
        "text": "[SIMULATION] Hi there! Choose a mode to start — Catphisher or Defender.",
        "ts": datetime.datetime.now().isoformat()
    }]
    st.session_state.mode = "Catphisher"

if "chat_history" not in st.session_state:
    reset_chat()

# ---------------- STYLE ----------------
st.markdown("""
<style>
/* Modern Color Scheme */
:root {
    --primary: #7C3AED;
    --secondary: #5B21B6;
    --bg-dark: #1E1B24;
    --bg-light: #2D2B3A;
    --text-light: #E2E8F0;
    --accent: #06B6D4;
}

/* Global Styles */
.stApp {
    background-color: var(--bg-dark) !important;
}

.chat-app {
    width: 90%;
    max-width: 600px;
    margin: 20px auto;
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    background: var(--bg-light);
    color: var(--text-light);
    font-family: 'Inter', system-ui, -apple-system;
    border: 1px solid rgba(255,255,255,0.1);
    backdrop-filter: blur(10px);
}

.header {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: white;
    padding: 16px;
    border-radius: 20px 20px 0 0;
    text-align: center;
    font-weight: 700;
    font-size: 1.2rem;
    text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.chat-window {
    height: 500px;
    overflow-y: auto;
    padding: 20px;
    background: var(--bg-dark);
    scroll-behavior: smooth;
}

.chat-window::-webkit-scrollbar {
    width: 6px;
}

.chat-window::-webkit-scrollbar-thumb {
    background: var(--primary);
    border-radius: 3px;
}

.message {
    margin: 12px 0;
    display: flex;
    animation: slidein 0.3s ease;
}

.message.incoming .bubble {
    background: var(--bg-light);
    color: var(--text-light);
    border-radius: 18px 18px 18px 0;
    padding: 12px 16px;
    max-width: 80%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border: 1px solid rgba(255,255,255,0.1);
}

.message.outgoing {
    justify-content: flex-end;
}

.message.outgoing .bubble {
    background: var(--primary);
    color: white;
    border-radius: 18px 18px 0 18px;
    padding: 12px 16px;
    max-width: 80%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.system {
    text-align: center;
    color: #94A3B8;
    margin: 16px 0;
    font-style: italic;
    animation: fadein 0.5s ease;
}

.red-flag-box {
    background: rgba(239, 68, 68, 0.1);
    border-left: 4px solid #EF4444;
    color: #FCA5A5;
    padding: 12px;
    border-radius: 8px;
    margin: 12px 0;
    animation: slidein 0.3s ease;
}

.input-area {
    background: var(--bg-light);
    padding: 16px;
    border-top: 1px solid rgba(255,255,255,0.1);
    border-radius: 0 0 20px 20px;
}

/* Animations */
@keyframes slidein {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadein {
    from {
        opacity: 0;
        transform: scale(0.95);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

/* Custom Streamlit Elements */
.stRadio > label {
    color: var(--text-light) !important;
}

.stButton > button {
    background: var(--primary) !important;
    color: white !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 0.5rem 1rem !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    background: var(--secondary) !important;
    transform: translateY(-1px) !important;
}

.stTextInput > div > div > input {
    background: var(--bg-dark) !important;
    color: var(--text-light) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
}

</style>
""", unsafe_allow_html=True)

# ---------------- UI ----------------
st.title("🐱 Cat-Phishing Awareness Simulator")

st.markdown("""
    <div style='text-align: center; color: #E2E8F0; margin-bottom: 2rem;'>
        <p style='font-size: 1.1rem; opacity: 0.9;'>
            Learn to identify and protect yourself from online catfishing attempts
        </p>
    </div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1,2,1])
with col2:
    mode = st.radio("Choose Mode:", ["Catphisher", "Defender"], 
                    index=(0 if st.session_state.mode=="Catphisher" else 1), 
                    horizontal=True)

# Add reset button
if st.button("Reset Chat"):
    reset_chat()
    st.rerun()

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
    if len(user_msg) > MAX_MESSAGE_LENGTH:
        st.error(f"Message too long. Please keep it under {MAX_MESSAGE_LENGTH} characters.")
    else:
        msg = sanitize_text(user_msg)
        st.session_state.chat_history.append({
            "role": "user", 
            "text": msg, 
            "ts": datetime.datetime.now().isoformat()
        })
        
        if st.session_state.mode == "Defender":
            # Get relevant history excluding system messages
            chat_history = [msg for msg in st.session_state.chat_history 
                           if msg["role"] in ["user", "bot"]]
            
            prompt = build_flag_prompt(msg, chat_history)
            result = get_llm_json(prompt)
            flags = result.get("flags", [])
            if flags and "(Offline" not in flags[0]:
                analysis = "🚨 **Potential Red Flags Detected:**<br>• " + "<br>• ".join(flags)
                reply = analysis + "<br><br>🧠 **Advice:** Be cautious — never share personal data or money with unverified users."
            else:
                reply = "✅ No major red flags detected. Stay alert!"
        else:
            chat_history = [msg for msg in st.session_state.chat_history 
                           if msg["role"] in ["user", "bot"]]
            
            prompt = build_catphisher_prompt(msg, chat_history)
            if apikey:
                try:
                    model = genai.GenerativeModel(MODEL_VERSION)
                    result = model.generate_content(prompt)
                    reply = result.text.strip() if result else DEFAULT_ERROR_MESSAGE
                except Exception as e:
                    reply = f"[SIMULATION] Error: {str(e)[:100]}"
            else:
                reply = "[SIMULATION] (Offline mode — Gemini API key not set)"
        
        st.session_state.chat_history.append({
            "role": "bot", 
            "text": reply, 
            "ts": datetime.datetime.now().isoformat()
        })
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("---")
st.info("⚠️ Simulation for educational awareness. Do not share real passwords, OTPs, or money online.")
