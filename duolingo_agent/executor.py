"""
Answer executor -- submits AI answers to Duolingo's DOM.

Each challenge type has a dedicated executor that maps the AI's JSON answer
back to DOM elements and interacts with them using JavaScript injection.
"""

import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


class Executor:
    """
    Executes answers for all Duolingo challenge types.

    Methods:
        execute(challenge_data, answer_dict) -- dispatches to the right handler
        click_check() -- clicks the Check/Submit button
        click_continue() -- clicks Continue/Next/Got it buttons
    """

    def __init__(self, browser, config, logger):
        self.browser = browser
        self.config = config
        self.log = logger

    # ------------------------------------------------------------------
    # Public dispatch
    # ------------------------------------------------------------------

    def execute(self, challenge_data, answer_dict):
        """
        Execute the answer based on challenge type.

        Args:
            challenge_data: ChallengeData from the parser
            answer_dict: {"answer": <value>} from the solver
        """
        answer = answer_dict.get("answer")
        if answer is None:
            self.log.error("No answer in response dict.")
            return False

        ctype = challenge_data.challenge_type
        handlers = {
            "mcq":          self._execute_mcq,
            "wordbank":     self._execute_wordbank,
            "typing":       self._execute_typing,
            "match":        self._execute_match,
            "fill_blank":   self._execute_fill_blank,
            "tap_complete": self._execute_tap_complete,
            "select":       self._execute_mcq,  # Same as MCQ
        }

        handler = handlers.get(ctype)
        if not handler:
            self.log.warn(f"No executor for challenge type: {ctype}. Trying typing fallback.")
            handler = self._execute_typing

        return handler(answer, challenge_data)

    # ------------------------------------------------------------------
    # MCQ -- select the correct option
    # ------------------------------------------------------------------

    def _execute_mcq(self, answer, data):
        """Click the option matching the AI's answer."""
        if isinstance(answer, list):
            answer = answer[0] if answer else ""
        answer_clean = str(answer).lower().strip()

        # Find option elements inside the challenge container
        container = self.browser.find("[data-test^='challenge challenge-']") or self.browser.find("body")
        option_elements = []
        for sel in ["div[data-test='challenge-choice']", "[role='radio']",
                     "button[data-test='challenge-choice']", "[role='listbox'] [role='option']"]:
            try:
                elems = container.find_elements(By.CSS_SELECTOR, sel)
                option_elements.extend(elems)
            except Exception:
                continue

        # Pass 1: Exact match
        for opt in option_elements:
            opt_text = self._get_option_text(opt)
            if opt_text == answer_clean:
                if self.browser.safe_click(opt):
                    self.log.success(f"Selected: {opt_text}")
                    time.sleep(self.config.delay_between_actions)
                    return True

        # Pass 2: Substring match
        for opt in option_elements:
            opt_text = self._get_option_text(opt)
            if opt_text and (answer_clean in opt_text or opt_text in answer_clean):
                if self.browser.safe_click(opt):
                    self.log.success(f"Selected (substring): {opt_text}")
                    time.sleep(self.config.delay_between_actions)
                    return True

        # Pass 3: Word overlap
        answer_words = {w for w in answer_clean.split() if len(w) > 2}
        if answer_words:
            best_match = None
            best_overlap = 0
            for opt in option_elements:
                opt_text = self._get_option_text(opt)
                if not opt_text:
                    continue
                opt_words = set(opt_text.split())
                overlap = len(answer_words & opt_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = opt
            if best_match and best_overlap > 0:
                if self.browser.safe_click(best_match):
                    self.log.success(f"Selected (word overlap): {self._get_option_text(best_match)}")
                    time.sleep(self.config.delay_between_actions)
                    return True

        self.log.warn(f"Could not match MCQ answer: {answer}")
        return False

    def _get_option_text(self, element):
        """Extract clean text from an option element."""
        try:
            text = element.text.strip()
            if "\n" in text:
                text = text.split("\n", 1)[-1].strip()
            return text.lower().strip()
        except StaleElementReferenceException:
            return ""

    # ------------------------------------------------------------------
    # Word Bank -- tap tiles in order
    # ------------------------------------------------------------------

    def _execute_wordbank(self, answer, data):
        """Tap word bank tiles in the order specified by the AI."""
        if isinstance(answer, str):
            tiles_to_tap = answer.split()
        elif isinstance(answer, list):
            tiles_to_tap = [str(t) for t in answer]
        else:
            tiles_to_tap = [str(answer)]

        clicked_indices = set()
        success_count = 0

        for target_tile in tiles_to_tap:
            target_clean = target_tile.lower().strip()
            tile_elements = self.browser.find_all(
                "button[data-test='challenge-tap-token'], button[data-test='word-bank-tile']"
            )

            clicked = False
            for i, elem in enumerate(tile_elements):
                if i in clicked_indices:
                    continue
                try:
                    if not elem.is_enabled() or not elem.is_displayed():
                        continue
                    # Check if tile was already tapped (some have a disabled/used class)
                    classes = elem.get_attribute("class") or ""
                    aria_disabled = elem.get_attribute("aria-disabled")
                    if aria_disabled == "true":
                        continue

                    tile_text = elem.text.strip().lower()
                    if tile_text == target_clean:
                        if self.browser.safe_click(elem):
                            clicked_indices.add(i)
                            success_count += 1
                            clicked = True
                            time.sleep(self.config.delay_between_actions)
                            break
                except StaleElementReferenceException:
                    continue

            if not clicked:
                self.log.debug(f"Could not find tile: {target_tile}")

        if success_count > 0:
            self.log.success(f"Tapped {success_count}/{len(tiles_to_tap)} tiles.")
        return success_count > 0

    # ------------------------------------------------------------------
    # Typing -- type the translated answer
    # ------------------------------------------------------------------

    def _execute_typing(self, answer, data):
        """Type the answer into the text input."""
        if isinstance(answer, list):
            answer = " ".join(str(a) for a in answer)
        answer = str(answer).strip()

        input_selectors = [
            "textarea[data-test='challenge-translate-input']",
            "input[data-test='challenge-text-input']",
            "textarea[data-test='challenge-listen-input']",
            "[contenteditable='true']",
        ]

        for sel in input_selectors:
            elem = self.browser.find(sel)
            if elem and elem.is_displayed():
                if self.browser.safe_type(elem, answer):
                    self.log.success(f"Typed: {answer}")
                    time.sleep(self.config.delay_between_actions)
                    return True

        self.log.warn("No text input found for typing.")
        return False

    # ------------------------------------------------------------------
    # Match Pairs -- click matching token pairs
    # ------------------------------------------------------------------

    def _execute_match(self, answer, data):
        """Click pairs of matching tokens."""
        if not isinstance(answer, list):
            self.log.warn("Match answer is not a list.")
            return False

        pairs_clicked = 0
        for pair in answer:
            if not isinstance(pair, list) or len(pair) < 2:
                continue

            t1 = str(pair[0]).strip().lower()
            t2 = str(pair[1]).strip().lower()

            # Find the two matching elements
            tokens = self.browser.find_all("button[data-test='challenge-tap-token']")
            elem1, elem2 = None, None

            for tok in tokens:
                try:
                    if not tok.is_enabled() or not tok.is_displayed():
                        continue
                    aria_disabled = tok.get_attribute("aria-disabled")
                    if aria_disabled == "true":
                        continue
                    tok_text = tok.text.strip().lower()
                    if tok_text == t1 and elem1 is None:
                        elem1 = tok
                    elif tok_text == t2 and elem2 is None:
                        elem2 = tok
                except StaleElementReferenceException:
                    continue

            if elem1 and elem2:
                self.browser.safe_click(elem1)
                time.sleep(self.config.delay_between_actions)
                self.browser.safe_click(elem2)
                time.sleep(self.config.delay_between_actions)
                pairs_clicked += 1
            else:
                self.log.debug(f"Could not find match pair: {t1} <-> {t2}")

        if pairs_clicked > 0:
            self.log.success(f"Matched {pairs_clicked} pairs.")
        return pairs_clicked > 0

    # ------------------------------------------------------------------
    # Fill Blank -- type missing word into partial sentence
    # ------------------------------------------------------------------

    def _execute_fill_blank(self, answer, data):
        """Fill in the blank in a partial sentence."""
        if isinstance(answer, list):
            answer = answer[0] if answer else ""
        answer = str(answer).strip()

        # First try: If there are options/tiles to tap, use MCQ/tap approach
        if data.options:
            return self._execute_mcq(answer, data)
        if data.tiles:
            return self._execute_wordbank([answer], data)

        # Second try: Find the inline input/textarea
        return self._execute_typing(answer, data)

    # ------------------------------------------------------------------
    # Tap Complete -- tap the correct completion word
    # ------------------------------------------------------------------

    def _execute_tap_complete(self, answer, data):
        """Tap the correct word to complete the sentence."""
        if isinstance(answer, list):
            answer = answer[0] if answer else ""
        answer_clean = str(answer).lower().strip()

        # Try tapping from available tokens
        tokens = self.browser.find_all(
            "button[data-test='challenge-tap-token'], button[data-test='challenge-choice']"
        )
        for tok in tokens:
            try:
                if not tok.is_enabled() or not tok.is_displayed():
                    continue
                tok_text = tok.text.strip().lower()
                if tok_text == answer_clean or answer_clean in tok_text:
                    if self.browser.safe_click(tok):
                        self.log.success(f"Tapped completion: {tok_text}")
                        time.sleep(self.config.delay_between_actions)
                        return True
            except StaleElementReferenceException:
                continue

        self.log.warn(f"Could not find tap-complete token: {answer}")
        return False

    # ------------------------------------------------------------------
    # Button clicks: Check, Continue, Skip
    # ------------------------------------------------------------------

    def click_check(self):
        """Click the Check / Submit button."""
        time.sleep(self.config.delay_after_answer)

        # Primary: data-test button
        btn = self.browser.find("button[data-test='player-next']")
        if btn:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    btn_text = btn.text.strip().lower()
                    # Only click if it says "check" (not "continue" -- that's a different state)
                    if "check" in btn_text or "submit" in btn_text or btn_text == "":
                        self.browser.safe_click(btn)
                        self.log.debug("Clicked Check.")
                        return True
            except Exception:
                pass

        # Fallback: any button with Check text
        if self.browser.click_button_by_text("check", "submit"):
            self.log.debug("Clicked Check (fallback).")
            return True

        # Last resort: click player-next regardless of text
        if btn:
            self.browser.safe_click(btn)
            self.log.debug("Clicked player-next (forced).")
            return True

        return False

    def click_continue(self):
        """Click Continue / Next / Got it to proceed."""
        btn = self.browser.find("button[data-test='player-next']")
        if btn:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    self.browser.safe_click(btn)
                    self.log.debug("Clicked Continue.")
                    time.sleep(self.config.delay_page_load)
                    return True
            except Exception:
                pass

        # Try text-based fallback
        for text in ["continue", "next", "got it", "review lesson", "no thanks"]:
            if self.browser.click_button_by_text(text):
                self.log.debug(f"Clicked '{text}'.")
                time.sleep(self.config.delay_page_load)
                return True

        return False

    def skip_challenge(self):
        """Skip listening or speaking challenges that can't be automated."""
        skipped = False
        for phrase in ["can't listen now", "can't speak now", "skip"]:
            if self.browser.click_button_by_text(phrase):
                self.log.info(f"Skipped: {phrase}")
                time.sleep(1)
                skipped = True
                break
        return skipped
