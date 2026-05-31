"""
Challenge parser for extracting question data from Duolingo's DOM.
Handles all known challenge types and extracts correction feedback.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChallengeData:
    """Structured representation of a Duolingo challenge."""
    challenge_type: str = "unknown"     # mcq, wordbank, typing, match, fill_blank, tap_complete, select, unknown
    raw_type: str = "unknown"           # Raw data-test attribute value
    header: str = ""                    # Main question text (h1)
    prompt: str = ""                    # Sub-question / translation prompt
    options: List[str] = field(default_factory=list)      # MCQ choices
    tiles: List[str] = field(default_factory=list)        # Word bank tiles
    match_tokens: List[str] = field(default_factory=list) # Match pair tokens
    has_input: bool = False             # Whether a text input is present

    @property
    def is_empty(self):
        return not self.header and not self.prompt and not self.options and not self.tiles and not self.match_tokens

    @property
    def fingerprint(self):
        """Unique identifier for this challenge (used for caching/dedup)."""
        return f"{self.prompt}|{self.options}|{self.tiles}|{self.match_tokens}"

    def __str__(self):
        parts = []
        if self.header:
            parts.append(f"Q: {self.header}")
        if self.prompt:
            parts.append(f"Prompt: {self.prompt}")
        if self.options:
            parts.append(f"Options: {self.options}")
        if self.tiles:
            parts.append(f"Tiles: {self.tiles}")
        if self.match_tokens:
            parts.append(f"Match: {self.match_tokens}")
        return " | ".join(parts) if parts else "(empty challenge)"


class ChallengeParser:
    """
    Extracts challenge data from the Duolingo DOM.

    Detects challenge type via data-test attributes and extracts all
    relevant content: headers, prompts, options, tiles, tokens, and inputs.
    Also reads correction banners after wrong answers.
    """

    # CSS selectors for challenge containers
    CHALLENGE_CONTAINER = "[data-test^='challenge challenge-']"

    # Challenge type mappings from data-test attribute suffixes
    TYPE_MAP = {
        "translate":            "typing",
        "completeReverseTranslation": "fill_blank",
        "listenTap":            "wordbank",
        "name":                 "mcq",
        "form":                 "mcq",
        "judge":                "mcq",
        "select":               "mcq",
        "characterSelect":      "mcq",
        "selectTranscription":  "mcq",
        "selectPronunciation":  "mcq",
        "gapFill":              "mcq",
        "match":                "match",
        "tapComplete":          "tap_complete",
        "assist":               "mcq",
        "listen":               "typing",
        "speak":                "skip",
        "dialogue":             "mcq",
        "readComprehension":    "mcq",
        "listenComprehension":  "mcq",
        "definition":           "mcq",
        "listenComplete":       "fill_blank",
        "tapCloze":             "wordbank",
        "tapClozeTable":        "wordbank",
        "characterMatch":       "match",
        "transliterationAssist":"typing",
        "partialReverseTranslate": "fill_blank",
    }

    def __init__(self, browser, logger):
        self.browser = browser
        self.log = logger

    def parse(self) -> Optional[ChallengeData]:
        """
        Extract the current challenge data from the page.
        Returns a ChallengeData object or None if no challenge is detected.
        """
        data = ChallengeData()

        # Find the challenge container
        challenge_node = self.browser.find(self.CHALLENGE_CONTAINER)
        if not challenge_node:
            # Fall back to body if no challenge container found
            challenge_node = self.browser.find("body")
            if not challenge_node:
                return None

        # Detect raw challenge type from data-test attribute
        try:
            raw_attr = challenge_node.get_attribute("data-test") or ""
            # Format: "challenge challenge-typeName"
            parts = raw_attr.split(" ")
            if len(parts) >= 2:
                data.raw_type = parts[1].replace("challenge-", "")
            else:
                data.raw_type = raw_attr
        except Exception:
            data.raw_type = "unknown"

        # Extract question header
        data.header = self._extract_header(challenge_node)

        # Extract prompt / sub-question
        data.prompt = self._extract_prompt(challenge_node, data.header)

        # Detect if this is a match challenge FIRST (before options/tiles)
        if data.raw_type == "match" or data.raw_type == "characterMatch":
            data.match_tokens = self._extract_match_tokens(challenge_node)
            data.challenge_type = "match"
            return data

        # Extract MCQ options
        data.options = self._extract_options(challenge_node)

        # Extract word bank tiles
        data.tiles = self._extract_tiles(challenge_node)

        # Check for text input
        data.has_input = self._has_text_input(challenge_node)

        # Determine the challenge type
        data.challenge_type = self._determine_type(data)

        if data.is_empty:
            return None

        return data

    def _extract_header(self, node) -> str:
        """Extract the main question header text."""
        selectors = [
            "h1[data-test='challenge-header']",
            "[data-test='challenge-header']",
            "h1",
        ]
        for sel in selectors:
            try:
                elements = node.find_elements_by_css_selector(sel) if hasattr(node, 'find_elements_by_css_selector') else []
                if not elements:
                    from selenium.webdriver.common.by import By
                    elements = node.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    text = elem.text.strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def _extract_prompt(self, node, header) -> str:
        """Extract the sub-question / translation prompt."""
        selectors = [
            "[data-test='challenge-translate-prompt']",
            "[data-test='challenge-listen-prompt']",
            "[data-test='challenge-prompt']",
            "[data-test='hint-sentence']",
            "[data-test='challenge-secondary-prompt']",
            "[dir='ltr'] > span",
        ]
        texts = []
        from selenium.webdriver.common.by import By
        for sel in selectors:
            try:
                elements = node.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    text = elem.text.strip()
                    if text and text != header and text not in texts:
                        texts.append(text)
            except Exception:
                continue
        return " ".join(texts)

    def _extract_options(self, node) -> List[str]:
        """Extract MCQ option texts."""
        from selenium.webdriver.common.by import By
        selectors = [
            "div[data-test='challenge-choice']",
            "[role='radio']",
            "button[data-test='challenge-choice']",
            "[data-test='challenge-judge-text']",
        ]
        options = []
        for sel in selectors:
            try:
                elements = node.find_elements(By.CSS_SELECTOR, sel)
                for opt in elements:
                    text = opt.text.strip()
                    if text:
                        # Remove option number prefix (e.g., "1\nAnswer")
                        if "\n" in text:
                            text = text.split("\n", 1)[-1].strip()
                        if text and text not in options:
                            options.append(text)
            except Exception:
                continue
        return options

    def _extract_tiles(self, node) -> List[str]:
        """Extract word bank tile texts."""
        from selenium.webdriver.common.by import By
        tiles = []
        selectors = [
            "button[data-test='challenge-tap-token']",
            "button[data-test='word-bank-tile']",
            "[data-test='challenge-tap-token-text']",
        ]
        for sel in selectors:
            try:
                elements = node.find_elements(By.CSS_SELECTOR, sel)
                for tile in elements:
                    if tile.is_enabled() and tile.is_displayed():
                        text = tile.text.strip()
                        if text:
                            tiles.append(text)
            except Exception:
                continue
        # Deduplicate while preserving order (tiles can have duplicates intentionally)
        return tiles if tiles else []

    def _extract_match_tokens(self, node) -> List[str]:
        """Extract match exercise tokens."""
        from selenium.webdriver.common.by import By
        tokens = []
        try:
            elements = node.find_elements(
                By.CSS_SELECTOR, "button[data-test='challenge-tap-token']"
            )
            for elem in elements:
                if elem.is_enabled() and elem.is_displayed():
                    text = elem.text.strip()
                    if text:
                        tokens.append(text)
        except Exception:
            pass
        return tokens

    def _has_text_input(self, node) -> bool:
        """Check if a typing input is present."""
        from selenium.webdriver.common.by import By
        input_selectors = [
            "textarea[data-test='challenge-translate-input']",
            "input[data-test='challenge-text-input']",
            "textarea[data-test='challenge-listen-input']",
            "[contenteditable='true']",
        ]
        for sel in input_selectors:
            try:
                elements = node.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    if elem.is_displayed():
                        return True
            except Exception:
                continue
        return False

    def _determine_type(self, data: ChallengeData) -> str:
        """Determine the challenge type from extracted data and raw type."""
        # Check the raw type mapping first
        mapped = self.TYPE_MAP.get(data.raw_type)
        if mapped == "skip":
            return "skip"

        # If raw type says fill_blank or tap_complete, trust it
        if mapped in ("fill_blank", "tap_complete"):
            return mapped

        # Heuristic detection based on what data we found
        if data.has_input and data.tiles:
            # Has both input AND tiles -- could be fill_blank with word bank
            return "fill_blank"
        elif data.has_input:
            return "typing"
        elif data.match_tokens:
            return "match"
        elif data.tiles:
            return "wordbank"
        elif data.options:
            return "mcq"
        elif mapped:
            return mapped

        return "unknown"

    # ------------------------------------------------------------------
    # Correction extraction
    # ------------------------------------------------------------------

    def extract_correction(self) -> Optional[str]:
        """
        After a wrong answer, Duolingo shows the correct answer in a banner.
        Extract that correction text for learning.
        """
        from selenium.webdriver.common.by import By
        correction_selectors = [
            "[data-test='challenge-judge-feedback-message']",
            "[class*='_1UqAr']",  # Correction text container (may change)
            "//div[contains(@class, 'blame')]//span",
            "//div[contains(@class, 'correct')]",
        ]

        # Try CSS selectors first
        for sel in correction_selectors[:2]:
            try:
                elements = self.browser.find_all(sel)
                for elem in elements:
                    text = elem.text.strip()
                    if text and len(text) > 1:
                        return text
            except Exception:
                continue

        # Try XPath selectors
        for sel in correction_selectors[2:]:
            try:
                elements = self.browser.find_all_xpath(sel)
                for elem in elements:
                    text = elem.text.strip()
                    if text and len(text) > 1:
                        return text
            except Exception:
                continue

        # Try finding the green/red feedback banner by looking at the bottom area
        try:
            # The footer area often contains "Correct solution: X"
            footer = self.browser.find("[data-test='blame blame-incorrect']")
            if footer:
                text = footer.text.strip()
                if text:
                    # Extract the answer part after "Correct solution:" or similar
                    for prefix in ["Correct solution:", "Correct answer:", "Answer:"]:
                        if prefix.lower() in text.lower():
                            return text.split(":", 1)[-1].strip()
                    return text
        except Exception:
            pass

        return None
