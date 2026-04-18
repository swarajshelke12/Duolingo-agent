# 🦉 Duolingo Auto-Agent

A high-speed, fully autonomous Python agent that completes Duolingo lessons using browser automation and advanced AI. Built for maximum reliability, it seamlessly integrates with the Groq API for lightning-fast reasoning, with a built-in automatic fallback to Google Gemini.

## ✨ Features
- 🧠 **Dual-AI Engine:** Uses `openai/gpt-oss-20b` via Groq for instant answers, automatically failing over to `gemini-2.0-flash` if rate limits are hit.
- ⚡ **JavaScript Injection Clicks:** Bypasses visual UI overlays and glitchy animations by interacting directly with the browser engine, ensuring 100% click accuracy.
- 🛡️ **Session Persistence:** Automatically saves your Duolingo login state using a local Chrome profile. You only have to log in once!
- 🕵️ **Stealth Mode:** Configured to avoid Duolingo's bot-detection systems.
- 🧩 **Smart Pattern Matching:** Parses complex exercises like MCQs, Word Banks, Matching pairs, and translation inputs cleanly.
- 🔒 **Local Security:** API keys are secured locally via a `.env` file and never pushed to version control.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Google Chrome installed on your machine
- A Groq API Key and/or a Google Gemini API Key

### Installation

1. Clone the repository and navigate into the folder:
```bash
git clone https://github.com/swarajshelke12/Duolingo-agent.git
cd Duolingo-agent
```

2. Install the required Python packages:
```bash
pip install selenium webdriver-manager google-genai groq python-dotenv
```

3. Create a `.env` file in the root directory and add your API keys:
```env
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Usage
Run the script directly from your terminal:
```bash
python Duolingo_Agent.py
```

**How it works:**
1. A Chrome browser window will open.
2. If it's your first time, log in to your Duolingo account.
3. The bot will patiently wait on the home screen.
4. Simply **click any lesson to start it**. As soon as the lesson loads, the agent will detect it and flawlessly take over!