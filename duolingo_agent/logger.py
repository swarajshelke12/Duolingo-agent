"""
Colored, timestamped console logger for the Duolingo Agent.
Provides visual distinction between info, success, warning, error, and debug messages.
"""

import sys
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Backgrounds
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class Logger:
    """
    Structured logger with colored output, timestamps, and challenge statistics.

    Usage:
        log = Logger()
        log.info("Starting agent")
        log.success("Challenge solved!")
        log.warn("Rate limit approaching")
        log.error("API call failed")
    """

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.stats = {
            "solved": 0,
            "failed": 0,
            "skipped": 0,
            "lessons_completed": 0,
        }

    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S")

    def _print(self, level_tag, color, message):
        timestamp = f"{Colors.GRAY}{self._timestamp()}{Colors.RESET}"
        tag = f"{color}{Colors.BOLD}{level_tag}{Colors.RESET}"
        print(f"  {timestamp}  {tag}  {message}")
        sys.stdout.flush()

    def info(self, message):
        """General information message."""
        self._print("INFO", Colors.BLUE, message)

    def success(self, message):
        """Success/positive outcome message."""
        self._print(" OK ", Colors.GREEN, message)

    def warn(self, message):
        """Warning message for non-critical issues."""
        self._print("WARN", Colors.YELLOW, message)

    def error(self, message):
        """Error message for failures."""
        self._print("FAIL", Colors.RED, message)

    def debug(self, message):
        """Debug message, only shown in verbose mode."""
        if self.verbose:
            self._print(" -- ", Colors.GRAY, message)

    def challenge(self, challenge_type, question):
        """Log a challenge being processed."""
        type_tag = f"{Colors.CYAN}{Colors.BOLD}[{challenge_type.upper()}]{Colors.RESET}"
        self._print(" >> ", Colors.MAGENTA, f"{type_tag} {question}")

    def answer(self, answer_text):
        """Log the AI's answer."""
        self._print(" << ", Colors.GREEN, f"Answer: {Colors.BOLD}{answer_text}{Colors.RESET}")

    def solved(self):
        """Increment solved counter."""
        self.stats["solved"] += 1

    def failed(self):
        """Increment failed counter."""
        self.stats["failed"] += 1

    def skipped(self):
        """Increment skipped counter."""
        self.stats["skipped"] += 1

    def lesson_done(self):
        """Increment lessons completed counter."""
        self.stats["lessons_completed"] += 1

    def print_stats(self):
        """Print a summary of challenge statistics."""
        s = self.stats
        total = s["solved"] + s["failed"] + s["skipped"]
        accuracy = (s["solved"] / total * 100) if total > 0 else 0

        print()
        print(f"  {Colors.BOLD}{Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print(f"  {Colors.BOLD}  Session Statistics{Colors.RESET}")
        print(f"  {Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print(f"    Lessons Completed : {Colors.BOLD}{s['lessons_completed']}{Colors.RESET}")
        print(f"    Challenges Solved : {Colors.GREEN}{Colors.BOLD}{s['solved']}{Colors.RESET}")
        print(f"    Challenges Failed : {Colors.RED}{Colors.BOLD}{s['failed']}{Colors.RESET}")
        print(f"    Challenges Skipped: {Colors.YELLOW}{Colors.BOLD}{s['skipped']}{Colors.RESET}")
        print(f"    Accuracy          : {Colors.BOLD}{accuracy:.1f}%{Colors.RESET}")
        print(f"  {Colors.CYAN}{'=' * 50}{Colors.RESET}")
        print()

    def banner(self):
        """Print the startup banner."""
        print()
        print(f"  {Colors.GREEN}{Colors.BOLD}{'=' * 50}{Colors.RESET}")
        print(f"  {Colors.GREEN}{Colors.BOLD}   Duolingo Agent v2.0{Colors.RESET}")
        print(f"  {Colors.GRAY}   AI-Powered Autonomous Language Learning{Colors.RESET}")
        print(f"  {Colors.GREEN}{Colors.BOLD}{'=' * 50}{Colors.RESET}")
        print()
