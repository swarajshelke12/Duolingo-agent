"""
Centralized configuration for the Duolingo Agent.
Loads environment variables from .env and provides typed access to all settings.
"""

import os
import sys
from dotenv import load_dotenv


class Config:
    """
    Agent configuration loaded from environment variables and .env file.

    Validates that at least one API key is present and provides
    sensible defaults for all timing and behavior settings.
    """

    def __init__(self, groq_api_key=None, gemini_api_key=None, headless=False,
                 browser_path=None, max_lessons=0, auto_continue=True, verbose=True):
        # Load .env from project root
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        load_dotenv(env_path)

        # API Keys -- constructor args override env vars
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        
        # Credentials for optional auto-login
        self.username = os.environ.get("DUOLINGO_USERNAME")
        self.password = os.environ.get("DUOLINGO_PASSWORD")

        # Validate at least one key exists
        if not self.groq_api_key and not self.gemini_api_key:
            print("\n  [ERROR] No API keys found.")
            print("  Please add GROQ_API_KEY and/or GEMINI_API_KEY to your .env file.")
            print("  See .env.example for the template.\n")
            sys.exit(1)

        # Browser settings
        self.headless = headless
        self.browser_path = browser_path

        # Agent behavior
        self.max_lessons = max_lessons          # 0 = infinite
        self.auto_continue = auto_continue      # Auto-start next lesson
        self.verbose = verbose                  # Debug logging

        # AI Model configuration
        self.groq_model = "llama-3.3-70b-versatile"
        self.gemini_model = "gemini-2.0-flash"
        self.ai_temperature = 0.0               # Maximum determinism

        # Timing (seconds) -- human-like delays
        self.delay_between_actions = 0.15       # Delay between clicks/taps
        self.delay_after_answer = 0.8           # Delay after submitting answer
        self.delay_page_load = 2.0              # Wait for page transitions
        self.delay_challenge_read = 0.5         # Simulate reading the question
        self.delay_rate_limit = 15.0            # Pause on 429 rate limit

        # Selenium timeouts
        self.wait_timeout = 15                  # WebDriverWait timeout
        self.page_load_timeout = 30             # Page load timeout

        # Chrome window
        self.window_width = 1280
        self.window_height = 720

        # Duolingo URLs
        self.base_url = "https://www.duolingo.com"
        self.learn_url = f"{self.base_url}/learn"
        self.login_url = f"{self.base_url}/?is_login=true"

        # Correction cache path
        self.cache_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "correction_cache.json"
        )

    def __repr__(self):
        groq_status = "set" if self.groq_api_key else "missing"
        gemini_status = "set" if self.gemini_api_key else "missing"
        return (
            f"Config(groq={groq_status}, gemini={gemini_status}, "
            f"headless={self.headless}, max_lessons={self.max_lessons})"
        )
