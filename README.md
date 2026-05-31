<div align="center">

<img src="assets/hero_banner.png" alt="Duolingo Agent - AI-Powered Autonomous Language Learning" width="100%" />

<br/>
<br/>

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Selenium](https://img.shields.io/badge/Selenium-4.x-43B02A?style=for-the-badge&logo=selenium&logoColor=white)](https://selenium.dev)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge&logo=meta&logoColor=white)](https://groq.com)
[![Gemini](https://img.shields.io/badge/Google_Gemini-2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/github/license/swarajshelke12/Duolingo-agent?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/swarajshelke12/Duolingo-agent?style=for-the-badge&logo=github)](https://github.com/swarajshelke12/Duolingo-agent)

**An autonomous AI agent that completes Duolingo lessons by combining browser automation with dual-LLM reasoning.**

[Getting Started](#getting-started) | [How It Works](#how-it-works) | [Configuration](#configuration) | [Contributing](#contributing)

</div>

---

## Overview

Duolingo Agent is a fully autonomous browser automation system that logs into your Duolingo account, detects language-learning challenges in real time, solves them using large language models, and submits the correct answers -- all without manual intervention.

It supports **every challenge type** Duolingo throws at you: multiple choice, word bank construction, free-form typing, and match-the-pairs exercises. The dual-AI architecture uses **Groq's LLaMA 3.3 70B** as the primary solver with **Google Gemini 2.0 Flash** as an automatic fallback, ensuring near-zero downtime even under rate limits.

---

## Features

<table>
<tr>
<td width="50%">

### Dual-AI Solver Engine
Groq (LLaMA 3.3 70B Versatile) handles challenges at blazing speed. If a rate limit or error occurs, the system seamlessly falls back to Google Gemini 2.0 Flash -- no human intervention required.

</td>
<td width="50%">

### Complete Challenge Coverage
Handles all four Duolingo challenge types out of the box:
- **MCQ** -- Selects the correct option
- **Word Bank** -- Taps tiles in the right order
- **Typing** -- Types the translated answer
- **Match Pairs** -- Clicks matching pairs

</td>
</tr>
<tr>
<td width="50%">

### Anti-Detection Stealth
Disables automation flags, removes `navigator.webdriver` fingerprints, and uses a persistent Chrome profile to maintain session cookies. The agent mimics human timing with configurable delays.

</td>
<td width="50%">

### Session Persistence
Your login session survives across restarts. A local Chrome profile directory stores cookies and session data, so you log in once and the agent remembers you.

</td>
</tr>
<tr>
<td width="50%">

### Smart Challenge Detection
A robust DOM scraper identifies challenge types by inspecting `data-test` attributes, prompt structures, and input elements. It distinguishes between MCQ, word bank, typing, and match challenges with high accuracy.

</td>
<td width="50%">

### Graceful Error Recovery
Built-in retry logic handles stale elements, rate limits, and unexpected page states. The agent pauses intelligently when APIs are throttled and resumes automatically.

</td>
</tr>
</table>

---

## Architecture

<div align="center">
<img src="assets/architecture_diagram.png" alt="System Architecture" width="85%" />
</div>

<br/>

The system operates as a closed loop:

```
Login --> Challenge Detection --> AI Reasoning --> Answer Execution --> Check/Continue --> Repeat
```

| Component | Technology | Role |
|---|---|---|
| Browser Engine | Selenium + ChromeDriver | Navigates Duolingo, interacts with DOM elements |
| Challenge Parser | Custom DOM Scraper | Extracts question, options, tiles, and input fields |
| Primary AI | Groq (LLaMA 3.3 70B) | Solves challenges with structured JSON responses |
| Fallback AI | Google Gemini 2.0 Flash | Activates when primary API is unavailable |
| Anti-Detection | Chrome Options + JS Injection | Evades bot detection mechanisms |
| Session Manager | Chrome Profile Directory | Persists login state across runs |

---

## How It Works

<div align="center">
<img src="assets/workflow_demo.png" alt="Workflow Steps" width="85%" />
</div>

<br/>

**Step 1 -- Login.**
The agent opens Duolingo's login page and waits for you to authenticate manually (first time only). Your session is saved to `chrome_profile/` for future runs.

**Step 2 -- Detect.**
Once inside a lesson, the challenge parser scans the DOM for `data-test` attributes to identify the challenge type and extract the question header, prompt text, answer options, word bank tiles, or match tokens.

**Step 3 -- Solve.**
The extracted challenge data is formatted into a structured prompt and sent to Groq's LLaMA 3.3 70B model (or Gemini as fallback). The AI returns a JSON response containing the exact answer.

**Step 4 -- Submit.**
The answer executor maps the AI's response back to DOM elements using JavaScript injection for precise clicks. For typing challenges, it clears the input field and types the answer. Finally, it clicks "Check" and handles the continue/next flow.

---

## Getting Started

### Prerequisites

- **Python 3.8+** installed on your system
- **Google Chrome** browser installed
- At least one API key:
  - [Groq API Key](https://console.groq.com/keys) (recommended, free tier available)
  - [Google Gemini API Key](https://aistudio.google.com/apikey) (fallback)

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/swarajshelke12/Duolingo-agent.git
cd Duolingo-agent
```

**2. Create a virtual environment (recommended)**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install selenium webdriver-manager google-genai groq
```

**4. Configure API keys**

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

> You need at least one key. Both are recommended for maximum reliability.

**5. Run the agent**

```bash
python Duolingo_Agent.py
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | One of two | API key for Groq (primary AI engine) |
| `GEMINI_API_KEY` | One of two | API key for Google Gemini (fallback AI engine) |

### Constructor Parameters

The `DuolingoAgent` class accepts the following parameters:

```python
agent = DuolingoAgent(
    api_key="...",          # Gemini API key (or set via .env)
    groq_api_key="...",     # Groq API key (or set via .env)
    headless=False,         # Run Chrome in headless mode (no visible window)
    browser_path=None       # Path to a custom Chrome/Chromium binary
)
```

### Chrome Options (Pre-configured)

The agent automatically applies these Chrome settings:

| Setting | Purpose |
|---|---|
| `--mute-audio` | Silences Duolingo sound effects |
| `--disable-notifications` | Blocks browser notification popups |
| `--window-size=1280,720` | Consistent viewport for element detection |
| `--no-sandbox` | Compatibility with restricted environments |
| `--disable-blink-features=AutomationControlled` | Removes automation fingerprint |
| `user-data-dir=chrome_profile` | Persists session across restarts |

---

## Project Structure

```
Duolingo-agent/
|
|-- Duolingo_Agent.py      # Core agent: browser control, AI solving, challenge handling
|-- .env                   # API keys (not tracked by git)
|-- .gitignore             # Excludes secrets, cache, and profile data
|-- chrome_profile/        # Persistent Chrome session data (auto-generated)
|-- assets/                # README images and visual resources
|   |-- hero_banner.png
|   |-- architecture_diagram.png
|   +-- workflow_demo.png
+-- README.md              # This file
```

---

## Challenge Types Explained

### Multiple Choice (MCQ)
The AI selects the correct option from a list. The agent matches the AI's answer against visible option text using exact and partial word matching as a fallback.

### Word Bank
The AI returns an ordered list of tiles to tap. Each tile is matched by exact text against available `challenge-tap-token` buttons and clicked in sequence.

### Typing
The AI generates the translated text. The agent clears the input field with `Ctrl+A > Delete` and types the answer directly.

### Match Pairs
The AI returns pairs of matching tokens (e.g., a word and its translation). The agent clicks each pair in sequence with a short delay between clicks.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ChromeDriver version mismatch` | The agent uses `webdriver-manager` to auto-download the correct version. Ensure Chrome is up to date. |
| `Rate limit hit (429)` | The agent automatically pauses and retries. If persistent, add both API keys for failover. |
| `Browser was closed or disconnected` | The agent detects this and exits gracefully. Restart the script. |
| `Failed to start a lesson automatically` | Click the lesson manually in the browser. The agent will detect the lesson URL and take over. |
| `Login not persisting` | Ensure `chrome_profile/` is not in `.gitignore` deletions and is writable. |

---

## Disclaimer

> This project is built for **educational and research purposes only**. It demonstrates browser automation techniques combined with large language model integration. Use responsibly and in accordance with Duolingo's Terms of Service. The authors are not responsible for any consequences arising from the use of this software.

---

## Contributing

Contributions are welcome. To get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please ensure your code follows the existing style and includes appropriate error handling.

---

## License

This project is open source. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with precision by [swarajshelke12](https://github.com/swarajshelke12)**

[![GitHub](https://img.shields.io/badge/Follow_on_GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/swarajshelke12)

<br/>

<sub>If this project helped you, consider giving it a star.</sub>

</div>