"""
Catphishing Awareness Demo - Gemini + SCC few-shot priming (SIMULATION)

Place the SCC dataset JSONL at: data/scc_clean.jsonl
(Each line is a JSON object - adapt loader if SCC format differs.)
"""

import streamlit as st
import google.generativeai as genai
import json, random, re, html, os
from typing import List, Dict
import os 

# -------------------------
# CONFIG / SECRETS
# -------------------------
st.set_page_config(page_title="Catphishing Awareness Demo (SIMULATION)", layout="centered")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key="AIzaSyBEbPbz4XlP_qkVtqaC-kqSF1-0rJ6YB0Q")

DATA_PATH = "cat.json"  # change if needed

# -------------------------
# UTIL: sanitize PII & normalize
# -------------------------
EMAIL_RE = re.compile(r"[a-zA-Z0-9.\-_+]+@[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-\(\)]{6,}\d)")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
NAME_RE = re.compile(r"\b([A-Z][a-z]{2,}\s?[A-Z]?[a-z]{0,})\b")  # rough

def sanitize_text(s: str) -> str:
    if not s: return ""
    s = html.unescape(s)
    s = EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = PHONE_RE.sub("[REDACTED_PHONE]", s)
    s = URL_RE.sub("[REDACTED_URL]", s)
    # keep names mostly but avoid exposing unique PII: optionally mask exact full names that look real
    # (we'll simply avoid over-masking; manual review recommended)
    return s

# -------------------------
# LOAD SCC dataset (safe)
# -------------------------
@st.cache_data(show_spinner=False)
def load_scc(path: str) -> List[Dict]:
    samples = []
    if not os.path.exists(path):
        st.warning(f"SCC dataset not found at {path}. Please place JSONL with sanitized dialogues there.")
        return samples
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except Exception:
                # try to be tolerant: skip bad lines
                continue
            # Expected: object with fields like 'dialogue' or 'text' - we normalize below
            samples.append(obj)
    return samples

raw_samples = load_scc(DATA_PATH)
if len(raw_samples) == 0:
    st.info("No SCC samples loaded. You can still run demo with synthetic few-shot examples.")
else:
    st.success(f"Loaded {len(raw_samples)} SCC records (sanitized).")

# -------------------------
# Helper: convert SCC record -> few-shot textual example
# Adjust this depending on SCC format.
# -------------------------
def make_example_from_record(rec: Dict) -> str:
    """
    Try to create a short conversational example from a record.
    This function is defensive: handle multiple possible formats.
    """
    # If the record already has a 'dialogue' key with list of turns:
    if "dialogue" in rec and isinstance(rec["dialogue"], list):
        turns = []
        for t in rec["dialogue"][:6]:  # take up to 6 turns
            # expect each turn is dict with speaker/text or tuple
            if isinstance(t, dict):
                sp = t.get("speaker", "scammer")
                text = t.get("text", "") or t.get("message", "")
            elif isinstance(t, list) or isinstance(t, tuple):
                sp = t[0]
                text = t[1]
            else:
                # fallback: string
                sp = "scammer"
                text = str(t)
            text = sanitize_text(text)
            turns.append(f"{sp.capitalize()}: {text}")
        return "\n".join(turns)
    # If it has 'text' or 'message'
    if "text" in rec:
        return sanitize_text(rec["text"])[:400]
    if "message" in rec:
        return sanitize_text(rec["message"])[:400]
    # fallback: stringify
    return sanitize_text(json.dumps(rec))[:400]

# Precompute few-shot pool (sanitized)
few_shot_pool = []
for r in raw_samples:
    try:
        ex = make_example_from_record(r)
        # Heuristic: skip very short or empty examples
        if ex and len(ex) > 10:
            few_shot_pool.append(ex)
    except Exception:
        continue

# If few_shot_pool empty, provide safe built-in examples
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
    """Return n few-shot examples (joined) sampled from the pool"""
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
# Prompt building for Gemini
# -------------------------
def build_prompt(mode: str, user_message: str, few_shot_count: int = 4) -> str:
    system_rules = (
        "You are a beautiful girl you should be nice and also make them fall for you when ever they talk to you.\n"
        "- ALWAYS prefix responses with [SIMULATION].\n"
        "- NEVER request or accept passwords, OTPs, bank details, or any PII.\n"
        "- If user attempts to share personal info, warn them and refuse.\n"
        "- Keep replies short (1-3 sentences) and natural.\n        "
    )
    if mode == "Catphisher":
        persona = (
            "Role: You are roleplaying a fake persona (catphisher) named 'Lizzy' for training only. "
            "Simulate typical catphishing behaviour (fast affection, requests to move chat, avoidance of video), "
            "BUT do NOT actually solicit money/OTPs/passwords. If you would ask for money or sensitive data, instead append "
            "'(SIMULATION — do NOT send money or passwords)'.\n"
        )
    else:
        persona = (
            "Role: You are a Defender Assistant. Analyze the user's incoming message or a short chat snippet, "
            "list up to 3 red flags with short reasons, propose 2 safe replies the user can send, and give reporting steps "
            "(block, report, inform IT/parent). Begin with [DEFENDER MODE].\n"
        )

    few_shots = build_few_shots(few_shot_count)
    prompt = f"{system_rules}\n{persona}\nFEW-SHOT EXAMPLES:\n{few_shots}\n\nUser message:\n{user_message}\n\nResponse:"
    return prompt

# -------------------------
# Gemini call
# -------------------------
def get_gemini_reply(prompt: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")  # adjust model as needed
        # Use generate_content/method depending on library version
        resp = model.generate_content(prompt)
        # The returned object shape may vary; attempt to extract text
        if hasattr(resp, "text"):
            return resp.text.strip()
        if isinstance(resp, dict) and "candidates" in resp:
            return resp["candidates"][0].get("content", "").strip()
        return str(resp)
    except Exception as e:
        return f"[SIMULATION] (Error contacting Gemini: {e})"

# -------------------------
# SESSION & UI
# -------------------------
st.title("🐱 Catphishing Awareness Demo — Gemini + SCC (SIMULATION)")
st.markdown("**Educational simulation only. Do NOT share real personal data.**")

mode = st.radio("Mode:", ["Catphisher (Simulation)", "Defender Mode"])
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []  # list of tuples (role, text)

user_input = st.text_input("Type message (do NOT enter passwords/OTP):")

cols = st.columns([1,1,1])
with cols[0]:
    if st.button("Send"):
        if not user_input.strip():
            st.warning("Enter a message.")
        else:
            # sanitize user input before sending to API; if user included sensitive pattern warn and remove
            sensitive_found = bool(re.search(r"(password|otp|pin|bank|account|card|cvv)", user_input.lower()))
            if sensitive_found:
                st.warning("It looks like you're trying to share sensitive info. Do NOT share such data. The input will be removed.")
                # remove the sensitive words
                user_input_sanitized = re.sub(r"(password|otp|pin|bank|account|card|cvv)", "[REDACTED_SENSITIVE]", user_input, flags=re.I)
            else:
                user_input_sanitized = user_input

            current_mode = "Catphisher" if "Catphisher" in mode else "Defender"
            prompt = build_prompt(current_mode, user_input_sanitized, few_shot_count=4)
            ai_reply = get_gemini_reply(prompt)

            # ensure reply starts with [SIMULATION] (safety)
            if not ai_reply.startswith("[SIMULATION]") and not ai_reply.startswith("[DEFENDER MODE]"):
                ai_reply = "[SIMULATION] " + ai_reply

            st.session_state.chat_history.append(("User", user_input_sanitized))
            st.session_state.chat_history.append(("Bot", ai_reply))

with cols[1]:
    if st.button("Auto-generate examples (augment dataset)"):
        # caution: generate a small set of synthetic dialogues (demo)
        prompt = (
            "You are a safe generator. Produce 5 short synthetic SIMULATION dialogues (3-6 turns each) between 'scammer' and 'target'. "
            "Label each with intents like FAST_AFFECTION, ASK_PHOTO, MOVE_PRIVATE, AVOID_VIDEO. Output JSONL lines with fields: dialogue (list of {speaker,text}), labels. "
            "Do NOT include real names, PII or instructions how to scam. Prefix each message with [SIMULATION]."
        )
        gen = get_gemini_reply(prompt)
        st.info("Generated (preview):")
        st.code(gen[:1000])

with cols[2]:
    if st.button("Clear chat"):
        st.session_state.chat_history = []

# Display chat with red-flag highlights
for role, text in st.session_state.chat_history:
    if role == "Bot":
        st.markdown(f"**🤖 Bot:** {text}")
        # If in Catphisher mode, detect flags in bot message
        if "Catphisher" in mode or text.startswith("[SIMULATION]"):
            flags = detect_red_flags(text)
            if flags:
                st.warning("🚩 Red Flags detected:\n" + "\n".join(f"- {f}" for f in flags))
    else:
        st.info(f"**{role}:** {text}")

st.markdown("---")
st.markdown("## How this app uses SCC dataset (short explanation)")
st.markdown(
    """
- The app **loads sanitized SCC records** (if present) and creates *few-shot examples* automatically.
- Those few-shot examples are inserted into the prompt given to Gemini so the bot's replies reflect realistic scammer tactics.
- This is **prompt-based priming** (not fine-tuning) — safe for demo and fast to iterate.
- You should manually review generated or SCC-derived examples before classroom use and mark everything SIMULATION.
"""
)

st.markdown("## Notes / Safety")
st.markdown(
    """
- NEVER deploy this publicly with real student data.
- If a user tries to enter passwords/OTP or personal PII, the app warns and removes sensitive tokens.
- Keep teacher/moderator present during live demos.
"""
)
