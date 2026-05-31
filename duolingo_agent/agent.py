"""
State machine orchestrator -- the brain of the Duolingo Agent.

Manages the full lifecycle: login -> navigate -> lesson -> challenge loop -> next lesson.
Handles all edge cases, error recovery, and continuous operation.
"""

import time
from enum import Enum, auto

from duolingo_agent.config import Config
from duolingo_agent.logger import Logger
from duolingo_agent.browser import Browser
from duolingo_agent.challenges import ChallengeParser
from duolingo_agent.solver import Solver
from duolingo_agent.executor import Executor


class State(Enum):
    """Agent states for the main loop."""
    LOGIN = auto()
    NAVIGATE = auto()
    LESSON_START = auto()
    CHALLENGE = auto()
    SUBMIT = auto()
    FEEDBACK = auto()
    LESSON_END = auto()
    DONE = auto()


class DuolingoAgent:
    """
    Fully autonomous Duolingo lesson solver.

    Usage:
        config = Config()
        agent = DuolingoAgent(config)
        agent.run()

    The agent operates as a state machine:
        LOGIN -> NAVIGATE -> LESSON_START -> CHALLENGE -> SUBMIT -> FEEDBACK -> (loop) -> LESSON_END -> NAVIGATE (loop)
    """

    def __init__(self, config: Config):
        self.config = config
        self.log = Logger(verbose=config.verbose)
        self.browser = Browser(config, self.log)
        self.parser = ChallengeParser(self.browser, self.log)
        self.solver = Solver(config, self.log, self.browser)
        self.executor = Executor(self.browser, config, self.log)

        self.state = State.LOGIN
        self.lessons_completed = 0
        self._last_fingerprint = None
        self._consecutive_failures = 0
        self._stuck_counter = 0

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        """Run the agent until max_lessons is reached or user quits."""
        self.log.banner()

        try:
            while self.state != State.DONE:
                if not self.browser.is_alive:
                    self.log.error("Browser disconnected. Shutting down.")
                    break

                if self.state == State.LOGIN:
                    self._handle_login()
                elif self.state == State.NAVIGATE:
                    self._handle_navigate()
                elif self.state == State.LESSON_START:
                    self._handle_lesson_start()
                elif self.state == State.CHALLENGE:
                    self._handle_challenge()
                elif self.state == State.SUBMIT:
                    self._handle_submit()
                elif self.state == State.FEEDBACK:
                    self._handle_feedback()
                elif self.state == State.LESSON_END:
                    self._handle_lesson_end()

        except KeyboardInterrupt:
            self.log.info("Interrupted by user.")
        except Exception as e:
            self.log.error(f"Fatal error: {e}")
        finally:
            self.log.print_stats()
            self.log.info("Agent stopped. Goodbye.")

    def shutdown(self):
        """Cleanly shut down the agent."""
        self.state = State.DONE
        self.browser.quit()

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_login(self):
        """Wait for the user to log in (first time only, session persists after)."""
        self.log.info("Checking login status...")

        # Try navigating to learn page
        self.browser.get(self.config.learn_url)
        time.sleep(3)

        if self.browser.url_contains("learn"):
            self.log.success("Logged in! Session restored from Chrome profile.")
            self.state = State.NAVIGATE
            return

        # Not logged in -- direct to login page
        self.log.info("Not logged in. Opening login page...")
        self.log.info("Please log in manually. The agent will wait...")
        self.browser.get(self.config.login_url)

        # Wait for login to complete
        while not self.browser.url_contains("learn", "lesson", "practice"):
            time.sleep(1)
            if not self.browser.is_alive:
                self.state = State.DONE
                return

        self.log.success("Login detected!")
        self.state = State.NAVIGATE

    def _handle_navigate(self):
        """Find and start the next lesson from the learn page."""
        # Check if max lessons reached
        if self.config.max_lessons > 0 and self.lessons_completed >= self.config.max_lessons:
            self.log.info(f"Completed {self.lessons_completed} lessons. Max reached.")
            self.state = State.DONE
            return

        # If already in a lesson, go straight to it
        if self.browser.url_contains("lesson", "practice"):
            self.log.info("Already in a lesson.")
            self.state = State.LESSON_START
            return

        # Make sure we're on the learn page
        if not self.browser.url_contains("learn"):
            self.browser.get(self.config.learn_url)
            time.sleep(self.config.delay_page_load)

        # Auto-continue or wait for user
        if not self.config.auto_continue and self.lessons_completed > 0:
            self.log.info("Press ENTER in the terminal to start the next lesson, or type 'q' to quit.")
            user_input = input()
            if user_input.strip().lower() == "q":
                self.state = State.DONE
                return

        self.log.info("Looking for a lesson to start...")

        # Try various selectors to find and click a start button
        started = self._try_start_lesson()
        if started:
            time.sleep(self.config.delay_page_load)
            self.state = State.LESSON_START
        else:
            self.log.warn("Could not auto-start a lesson. Please click one manually.")
            self.log.info("Waiting for lesson URL...")
            # Wait for the user to manually click a lesson
            wait_count = 0
            while not self.browser.url_contains("lesson", "practice"):
                time.sleep(1)
                wait_count += 1
                if wait_count > 300:  # 5 minute timeout
                    self.log.error("Timeout waiting for lesson. Shutting down.")
                    self.state = State.DONE
                    return
                if not self.browser.is_alive:
                    self.state = State.DONE
                    return
            self.state = State.LESSON_START

    def _try_start_lesson(self) -> bool:
        """Attempt to start a lesson using multiple selector strategies."""
        selectors = [
            "button[data-test='start-button']",
            "a[data-test='practice-hub-nav']",
            "a[data-test='global-practice']",
        ]

        # Strategy 1: Direct button click
        for sel in selectors:
            elem = self.browser.find(sel)
            if elem:
                try:
                    if elem.is_displayed():
                        self.browser.safe_click(elem)
                        self.log.info(f"Clicked start button: {sel}")
                        time.sleep(1)

                        # Check for a secondary start popup
                        if self.browser.click_button_by_text("start"):
                            time.sleep(1)
                        return True
                except Exception:
                    continue

        # Strategy 2: XPath text-based search
        for text in ["start", "practice", "continue"]:
            xpath = f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
            elems = self.browser.find_all_xpath(xpath)
            for elem in elems:
                try:
                    if elem.is_displayed() and elem.is_enabled():
                        self.browser.safe_click(elem)
                        self.log.info(f"Clicked '{text}' button.")
                        time.sleep(1)
                        # Check for secondary popup
                        if self.browser.click_button_by_text("start"):
                            time.sleep(1)
                        return True
                except Exception:
                    continue

        # Strategy 3: Click skill node bubbles
        nodes = self.browser.find_all("div[role='button']")
        for node in nodes:
            try:
                if node.is_displayed():
                    self.browser.safe_click(node)
                    time.sleep(0.5)
                    if self.browser.click_button_by_text("start"):
                        time.sleep(1)
                        return True
            except Exception:
                continue

        return False

    def _handle_lesson_start(self):
        """Transition: lesson page loaded, prepare for challenges."""
        self.log.info("Lesson started!")
        self._last_fingerprint = None
        self._consecutive_failures = 0
        self._stuck_counter = 0
        time.sleep(1)
        self.state = State.CHALLENGE

    def _handle_challenge(self):
        """Parse and solve the current challenge."""
        # Check if lesson is over
        if self.browser.url_contains("learn") and not self.browser.url_contains("lesson", "practice"):
            self.state = State.LESSON_END
            return

        if self.browser.url_contains("xp-summary", "stories"):
            self.state = State.LESSON_END
            return

        # Try to skip listening/speaking challenges
        if self.executor.skip_challenge():
            time.sleep(1)
            return  # Stay in CHALLENGE state, next iteration will get new challenge

        # Try clicking Continue/Next if available (e.g., after a feedback screen)
        if self._try_continue_buttons():
            return

        # Parse the challenge
        data = self.parser.parse()
        if not data or data.is_empty:
            self._stuck_counter += 1
            if self._stuck_counter > 15:
                self.log.warn("Stuck on empty challenge for too long. Trying to recover...")
                self._recover_stuck()
                self._stuck_counter = 0
            time.sleep(0.5)
            return

        self._stuck_counter = 0

        # Check if this is the same challenge (avoid re-solving)
        if data.fingerprint == self._last_fingerprint:
            # Same challenge, maybe answer wasn't submitted yet
            self._consecutive_failures += 1
            if self._consecutive_failures > 5:
                self.log.warn("Stuck on same challenge. Forcing re-solve...")
                self._last_fingerprint = None
                self._consecutive_failures = 0
            else:
                time.sleep(0.5)
                # Try clicking check in case it's pending
                self.executor.click_check()
                time.sleep(1)
                self.executor.click_continue()
                return

        # Log the challenge
        self.log.challenge(data.challenge_type, str(data))

        # Skip type
        if data.challenge_type == "skip":
            self.executor.skip_challenge()
            time.sleep(1)
            return

        # Solve with AI
        time.sleep(self.config.delay_challenge_read)
        answer = self.solver.solve(data)

        if not answer:
            self.log.error("AI failed to produce an answer.")
            self._consecutive_failures += 1
            if self._consecutive_failures > 3:
                self.log.warn("Multiple AI failures. Pausing 10s...")
                time.sleep(10)
            else:
                time.sleep(2)
            return

        self.log.answer(str(answer.get("answer", "")))

        # Execute the answer
        success = self.executor.execute(data, answer)
        self._last_fingerprint = data.fingerprint

        if success:
            self._consecutive_failures = 0
            self.state = State.SUBMIT
        else:
            self.log.warn("Answer execution failed.")
            self._consecutive_failures += 1
            time.sleep(1)

    def _handle_submit(self):
        """Click Check and wait for feedback."""
        time.sleep(self.config.delay_after_answer)
        self.executor.click_check()
        time.sleep(1)
        self.state = State.FEEDBACK

    def _handle_feedback(self):
        """Process feedback: read corrections, click continue."""
        # Check if we're back on the learn page
        if self.browser.url_contains("learn") and not self.browser.url_contains("lesson", "practice"):
            self.state = State.LESSON_END
            return

        # Try to extract correction (if the answer was wrong)
        correction = self.parser.extract_correction()
        if correction and self._last_fingerprint:
            self.log.warn(f"Wrong answer! Correct: {correction}")
            self.solver.learn_correction(self._last_fingerprint, correction)
            self.log.failed()
        else:
            self.log.solved()

        # Click Continue / Next
        self.executor.click_continue()
        time.sleep(0.5)

        # Sometimes need to click again
        self.executor.click_continue()
        time.sleep(0.5)

        self.state = State.CHALLENGE

    def _handle_lesson_end(self):
        """Lesson completed. Handle XP summary and decide whether to continue."""
        self.log.success("Lesson complete!")
        self.log.lesson_done()
        self.lessons_completed += 1

        # Handle XP summary screen
        time.sleep(1)
        for _ in range(5):
            if self.browser.url_contains("xp-summary"):
                self.executor.click_continue()
                time.sleep(1)
            else:
                break

        # Click through any post-lesson modals
        for text in ["continue", "no thanks", "not now", "maybe later", "close"]:
            self.browser.click_button_by_text(text)
            time.sleep(0.5)

        # Navigate back to learn page if needed
        if not self.browser.url_contains("learn"):
            self.browser.get(self.config.learn_url)
            time.sleep(self.config.delay_page_load)

        self.state = State.NAVIGATE

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _try_continue_buttons(self) -> bool:
        """Check if Continue/Next/Got it buttons are visible and clickable."""
        btn = self.browser.find("button[data-test='player-next']")
        if btn:
            try:
                if btn.is_displayed() and btn.is_enabled():
                    btn_text = btn.text.strip().lower()
                    if btn_text in ("continue", "next", "got it", "review lesson"):
                        self.browser.safe_click(btn)
                        self.log.debug(f"Clicked '{btn_text}'")
                        time.sleep(self.config.delay_page_load)
                        return True
            except Exception:
                pass
        return False

    def _recover_stuck(self):
        """Attempt to recover from a stuck state."""
        self.log.info("Attempting recovery...")

        # Try clicking any visible button
        for text in ["continue", "next", "skip", "got it", "check", "no thanks"]:
            if self.browser.click_button_by_text(text):
                self.log.info(f"Recovery: clicked '{text}'")
                time.sleep(1)
                return

        # Try clicking player-next
        btn = self.browser.find("button[data-test='player-next']")
        if btn:
            self.browser.safe_click(btn)
            self.log.info("Recovery: clicked player-next")
            time.sleep(1)
            return

        # Last resort: refresh
        self.log.warn("Recovery: refreshing page...")
        try:
            self.browser.driver.refresh()
            time.sleep(3)
        except Exception:
            pass
