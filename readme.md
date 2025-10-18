🐾 Catphishing Awareness Chatbot (AI-Powered Demo)
🧠 Project Overview

This project is an AI-powered awareness demo designed to educate students about catfishing attacks — a form of online deception where attackers impersonate someone to manipulate or scam victims.

Using Google’s Gemini LLM, this chatbot simulates real-world catfishing conversations and helps users learn how to detect manipulative patterns safely in a controlled environment.

⚠️ Disclaimer:
This project is intended strictly for educational and awareness purposes only.
It does not promote, encourage, or enable any malicious or deceptive online behavior.

🚀 Features

🗨️ Realistic Chat Simulation: Uses Gemini API to generate both attacker and victim responses.

🧩 Dataset Integration: Trained using the Social Computing Catfishing Corpus (SCC) dataset.

🎓 Awareness Mode: Highlights manipulation cues and explains red flags during interaction.

🌐 Interactive Web App: Built with Streamlit for easy browser-based demonstration.

🔒 Secure Key Handling: .env file used to protect sensitive API keys.

🧰 Tech Stack
Component	Technology Used
Frontend UI	Streamlit
LLM	Gemini API (Google Generative AI)
Dataset	Social Computing Catfishing Corpus (SCC)
Language	Python
Env Management	python-dotenv
Deployment	Streamlit Cloud / Localhost
📦 Installation & Setup
1️⃣ Clone the Repository
git clone https://github.com/<your-username>/catphish_demo.git
cd catphish_demo

2️⃣ Create a Virtual Environment
python -m venv venv
source venv/bin/activate    # On macOS/Linux
venv\Scripts\activate       # On Windows

3️⃣ Install Requirements
pip install -r requirements.txt

4️⃣ Add Your Gemini API Key

Create a .env file in the root directory:

GEMINI_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxx

▶️ Run the Application
streamlit run app.py


Then open the URL shown in the terminal (usually http://localhost:8501).

🧠 How It Works

The chatbot loads real or simulated messages from the catfishing dataset.

Gemini LLM generates context-aware responses for both sides.

Awareness layer highlights suspicious behaviors, emotional manipulation, and trust tactics.

The chat ends with educational insights on identifying catfishing patterns.

📊 Dataset Reference

Social Computing Catfishing Corpus (SCC)
🔗 https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/SCC2022

🛡️ Security Notes

All personal data used in demos is synthetic.

The project follows ethical AI principles for digital safety awareness.

Always store API keys securely using .env and never commit them to GitHub.

🤝 Contributing

Pull requests are welcome!
For major changes, please open an issue first to discuss what you’d like to improve.