"""
Dual-AI solver with screenshot-based vision fallback and correction caching.

Primary: Groq (LLaMA 3.3 70B) -- fast, free tier
Fallback: Google Gemini 2.0 Flash -- vision-capable, handles screenshots
Cache: Learns from Duolingo's correction feedback to avoid repeat mistakes.
"""

import json
import os
import time
import base64
from typing import Optional, Any


class Solver:
    """
    Solves Duolingo challenges using AI language models.

    Architecture:
        1. Check correction cache first (instant, no API call)
        2. Try Groq LLaMA 3.3 70B (fast text-based solving)
        3. Fall back to Gemini 2.0 Flash (text-based)
        4. Last resort: Gemini Vision (screenshot-based)

    All responses are structured JSON: {"answer": <value>}
    """

    def __init__(self, config, logger, browser):
        self.config = config
        self.log = logger
        self.browser = browser

        # Initialize API clients
        self.groq_client = None
        self.gemini_client = None

        if config.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=config.groq_api_key)
                self.log.success("Groq API connected.")
            except Exception as e:
                self.log.warn(f"Groq initialization failed: {e}")

        if config.gemini_api_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=config.gemini_api_key)
                self.log.success("Gemini API connected.")
            except Exception as e:
                self.log.warn(f"Gemini initialization failed: {e}")

        # Correction cache: maps challenge fingerprints to correct answers
        self._cache = self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self, challenge_data) -> Optional[dict]:
        """
        Solve a challenge. Returns parsed answer dict or None.

        Returns:
            {"answer": <str|list>} or None on failure
        """
        # Step 1: Check cache
        cached = self._check_cache(challenge_data.fingerprint)
        if cached is not None:
            self.log.debug("Cache hit -- using stored correction.")
            return cached

        # Step 2: Build prompt and try AI
        prompt = self._build_prompt(challenge_data)
        result = self._call_ai(prompt)

        if result:
            return result

        # Step 3: Screenshot fallback (Gemini Vision)
        if self.gemini_client:
            self.log.warn("Text-based solving failed. Trying screenshot vision...")
            return self._solve_with_screenshot(challenge_data)

        return None

    def learn_correction(self, fingerprint: str, correction: str):
        """Store a correction from Duolingo's feedback for future use."""
        if not fingerprint or not correction:
            return
        self._cache[fingerprint] = {"answer": correction}
        self._save_cache()
        self.log.debug(f"Learned correction: {correction}")

    # ------------------------------------------------------------------
    # Prompt engineering
    # ------------------------------------------------------------------

    def _build_prompt(self, data) -> str:
        """Build a challenge-type-specific prompt for maximum accuracy."""

        base = (
            "You are an expert Duolingo language challenge solver. "
            "You MUST output ONLY valid JSON with no other text, markdown, or explanation. "
            "Carefully infer the source and target languages from the words given.\n\n"
        )

        type_instructions = {
            "mcq": (
                "This is a MULTIPLE CHOICE challenge. Select the single correct answer.\n"
                f"Question: {data.header}\n"
                f"Context: {data.prompt}\n"
                f"Options: {json.dumps(data.options)}\n\n"
                "Return JSON: {\"answer\": \"EXACT text of the correct option from the Options list\"}\n"
                "The answer MUST be an EXACT string from the Options array. Do not modify it."
            ),
            "wordbank": (
                "This is a WORD BANK challenge. Arrange the given tiles to form the correct translation.\n"
                f"Question: {data.header}\n"
                f"Sentence to translate: {data.prompt}\n"
                f"Available tiles: {json.dumps(data.tiles)}\n\n"
                "Return JSON: {\"answer\": [\"tile1\", \"tile2\", ...]}\n"
                "CRITICAL: Use EXACTLY the strings from the Available tiles array. "
                "Do NOT alter capitalization, punctuation, or spelling. "
                "You may not need to use every tile. Order them to form a correct sentence."
            ),
            "typing": (
                "This is a TYPING challenge. Translate the given text.\n"
                f"Question: {data.header}\n"
                f"Text to translate: {data.prompt}\n\n"
                "Return JSON: {\"answer\": \"your translated text here\"}\n"
                "Provide only the translation, no quotes around it inside the JSON string unless part of the text."
            ),
            "match": (
                "This is a MATCHING challenge. Pair each word/phrase with its translation.\n"
                f"Tokens to match: {json.dumps(data.match_tokens)}\n\n"
                "Return JSON: {\"answer\": [[\"word1\", \"translation1\"], [\"word2\", \"translation2\"], ...]}\n"
                "Use EXACTLY the strings from the tokens list. Each token appears in exactly one pair."
            ),
            "fill_blank": (
                "This is a FILL IN THE BLANK challenge. Complete the sentence.\n"
                f"Question: {data.header}\n"
                f"Sentence with blank: {data.prompt}\n"
                f"Available choices: {json.dumps(data.options or data.tiles)}\n\n"
                "Return JSON: {\"answer\": \"the word or phrase that fills the blank\"}\n"
                "If choices are provided, pick from them exactly."
            ),
            "tap_complete": (
                "This is a TAP TO COMPLETE challenge. Select the correct word to complete the sentence.\n"
                f"Question: {data.header}\n"
                f"Sentence: {data.prompt}\n"
                f"Options: {json.dumps(data.options or data.tiles)}\n\n"
                "Return JSON: {\"answer\": \"the correct option text\"}\n"
                "Pick the EXACT string from the options."
            ),
        }

        challenge_type = data.challenge_type
        if challenge_type not in type_instructions:
            challenge_type = "typing"  # Default fallback

        return base + type_instructions[challenge_type]

    # ------------------------------------------------------------------
    # AI API calls
    # ------------------------------------------------------------------

    def _call_ai(self, prompt: str) -> Optional[dict]:
        """Try Groq first, then Gemini. Returns parsed JSON dict or None."""

        # Try Groq
        if self.groq_client:
            result = self._call_groq(prompt)
            if result:
                return result

        # Try Gemini (text mode)
        if self.gemini_client:
            result = self._call_gemini(prompt)
            if result:
                return result

        return None

    def _call_groq(self, prompt: str) -> Optional[dict]:
        """Call Groq API with structured JSON output."""
        try:
            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.groq_model,
                temperature=self.config.ai_temperature,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            return self._parse_json(raw)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                self.log.warn("Groq rate limit hit. Falling back...")
                time.sleep(2)
            else:
                self.log.warn(f"Groq error: {error_str}")
            return None

    def _call_gemini(self, prompt: str) -> Optional[dict]:
        """Call Gemini API for text-based solving."""
        try:
            response = self.gemini_client.models.generate_content(
                model=self.config.gemini_model,
                contents=prompt,
            )
            raw = response.text.strip()
            return self._parse_json(raw)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                self.log.warn(f"Gemini rate limit. Pausing {self.config.delay_rate_limit}s...")
                time.sleep(self.config.delay_rate_limit)
            else:
                self.log.warn(f"Gemini error: {error_str}")
            return None

    def _solve_with_screenshot(self, challenge_data) -> Optional[dict]:
        """
        Take a screenshot and use Gemini Vision to solve the challenge.
        This is the last-resort fallback when DOM scraping is insufficient.
        """
        if not self.gemini_client:
            return None

        screenshot_b64 = self.browser.take_screenshot_base64()
        if not screenshot_b64:
            self.log.error("Failed to capture screenshot.")
            return None

        prompt = (
            "You are looking at a Duolingo language learning challenge screenshot. "
            "Identify the challenge type and solve it. "
            "Output ONLY valid JSON: {\"answer\": <your answer>}\n\n"
            "Rules:\n"
            "- For multiple choice: answer is the exact text of the correct option\n"
            "- For word bank / tap: answer is a list of words in correct order\n"
            "- For typing: answer is the translated text\n"
            "- For matching: answer is a list of [word, translation] pairs\n"
            "- For fill-in-blank: answer is the missing word/phrase\n"
        )

        try:
            from google.genai import types as genai_types

            image_part = genai_types.Part.from_bytes(
                data=base64.b64decode(screenshot_b64),
                mime_type="image/png",
            )

            response = self.gemini_client.models.generate_content(
                model=self.config.gemini_model,
                contents=[prompt, image_part],
            )
            raw = response.text.strip()
            result = self._parse_json(raw)
            if result:
                self.log.success("Vision fallback solved the challenge!")
            return result

        except Exception as e:
            self.log.error(f"Vision fallback failed: {e}")
            return None

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def _parse_json(self, raw: str) -> Optional[dict]:
        """Parse a JSON response, handling markdown code fences."""
        if not raw:
            return None

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "answer" in parsed:
                return parsed
            # Wrap in answer key if it's a plain value
            return {"answer": parsed}
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(cleaned[start:end])
                    if isinstance(parsed, dict) and "answer" in parsed:
                        return parsed
                    return {"answer": parsed}
                except json.JSONDecodeError:
                    pass

            self.log.debug(f"Failed to parse AI response as JSON: {raw[:100]}")
            return None

    # ------------------------------------------------------------------
    # Correction cache
    # ------------------------------------------------------------------

    def _check_cache(self, fingerprint: str) -> Optional[dict]:
        """Look up a cached correction by challenge fingerprint."""
        return self._cache.get(fingerprint)

    def _load_cache(self) -> dict:
        """Load correction cache from disk."""
        try:
            if os.path.exists(self.config.cache_path):
                with open(self.config.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_cache(self):
        """Persist correction cache to disk."""
        try:
            with open(self.config.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log.debug(f"Failed to save cache: {e}")
