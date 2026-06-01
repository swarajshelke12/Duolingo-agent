"""
Rich, colored console logger for the Duolingo Agent.
Provides visual distinction between info, success, warning, error, and debug messages.
Features ASCII art banner, emoji indicators, progress bars, and a session dashboard.
"""

import sys
import time
import threading
from datetime import datetime, timedelta


class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Bright variants
    BRIGHT_GREEN = "\033[38;5;82m"
    BRIGHT_CYAN = "\033[38;5;87m"
    BRIGHT_YELLOW = "\033[38;5;228m"
    BRIGHT_RED = "\033[38;5;196m"
    BRIGHT_MAGENTA = "\033[38;5;207m"
    ORANGE = "\033[38;5;208m"
    LIME = "\033[38;5;118m"
    TEAL = "\033[38;5;38m"
    PINK = "\033[38;5;213m"
    GOLD = "\033[38;5;220m"

    # Backgrounds
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[48;5;236m"
    BG_DARK_GREEN = "\033[48;5;22m"
    BG_DARK_RED = "\033[48;5;52m"
    BG_DARK_YELLOW = "\033[48;5;58m"

    # Gradient greens (for banner)
    G1 = "\033[38;5;22m"
    G2 = "\033[38;5;28m"
    G3 = "\033[38;5;34m"
    G4 = "\033[38;5;40m"
    G5 = "\033[38;5;46m"
    G6 = "\033[38;5;82m"
    G7 = "\033[38;5;118m"
    G8 = "\033[38;5;154m"


# Unicode symbols
class Symbols:
    """Unicode symbols for visual indicators."""
    CHECK = "✓"
    CROSS = "✗"
    WARNING = "⚠"
    INFO = "ℹ"
    ARROW_RIGHT = "▶"
    ARROW_LEFT = "◀"
    DIAMOND = "◆"
    CIRCLE = "●"
    CIRCLE_EMPTY = "○"
    STAR = "★"
    BRAIN = "🧠"
    OWL = "🦉"
    ROCKET = "🚀"
    FIRE = "🔥"
    SPARKLE = "✨"
    TROPHY = "🏆"
    TARGET = "🎯"
    BOLT = "⚡"
    GEAR = "⚙"
    CLOCK = "🕐"
    CHART = "📊"
    SHIELD = "🛡"
    MAGNIFY = "🔍"
    PAINT = "🎨"
    PARTY = "🎉"
    CHAIN = "🔗"
    EYE = "👁"
    BLOCK_FULL = "█"
    BLOCK_HIGH = "▓"
    BLOCK_MED = "▒"
    BLOCK_LOW = "░"
    BAR_H = "─"
    BAR_V = "│"
    CORNER_TL = "╭"
    CORNER_TR = "╮"
    CORNER_BL = "╰"
    CORNER_BR = "╯"
    TEE_L = "├"
    TEE_R = "┤"
    TEE_T = "┬"
    TEE_B = "┴"


class Logger:
    """
    Structured logger with colored output, timestamps, and challenge statistics.

    Features:
        - ASCII art startup banner with gradient colors
        - Emoji-rich log levels for visual scanning
        - Progress bars and spinners for ongoing operations
        - Box-drawn session statistics dashboard
        - Per-challenge-type breakdown tracking

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
        self._challenge_types = {}  # Track per-type stats
        self._session_start = datetime.now()
        self._lesson_start = None
        self._current_lesson = 0
        self._challenge_in_lesson = 0
        self._spinner_active = False
        self._spinner_thread = None

    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S")

    def _elapsed(self):
        """Get elapsed session time as a formatted string."""
        delta = datetime.now() - self._session_start
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _print(self, level_tag, color, message, icon=""):
        timestamp = f"{Colors.GRAY}{self._timestamp()}{Colors.RESET}"
        tag = f"{color}{Colors.BOLD}{level_tag}{Colors.RESET}"
        icon_str = f"{icon} " if icon else ""
        print(f"  {timestamp}  {tag}  {icon_str}{message}")
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Log levels with emoji indicators
    # ------------------------------------------------------------------

    def info(self, message):
        """General information message."""
        self._print("INFO", Colors.BLUE, message, f"{Colors.BLUE}{Symbols.INFO}{Colors.RESET}")

    def success(self, message):
        """Success/positive outcome message."""
        self._print(f" {Symbols.CHECK}  ", Colors.GREEN, message, f"{Colors.GREEN}{Symbols.CHECK}{Colors.RESET}")

    def warn(self, message):
        """Warning message for non-critical issues."""
        self._print(f" {Symbols.WARNING}  ", Colors.YELLOW, f"{Colors.YELLOW}{message}{Colors.RESET}", f"{Colors.YELLOW}{Symbols.WARNING}{Colors.RESET}")

    def error(self, message):
        """Error message for failures."""
        self._print(f" {Symbols.CROSS}  ", Colors.RED,
                     f"{Colors.BG_DARK_RED}{Colors.WHITE} {message} {Colors.RESET}",
                     f"{Colors.RED}{Symbols.CROSS}{Colors.RESET}")

    def debug(self, message):
        """Debug message, only shown in verbose mode."""
        if self.verbose:
            self._print(" ── ", Colors.GRAY, f"{Colors.DIM}{message}{Colors.RESET}", f"{Colors.GRAY}{Symbols.GEAR}{Colors.RESET}")

    def challenge(self, challenge_type, question):
        """Log a challenge being processed."""
        self._challenge_in_lesson += 1
        ctype_upper = challenge_type.upper()
        type_colors = {
            "MCQ": Colors.CYAN,
            "WORDBANK": Colors.MAGENTA,
            "TYPING": Colors.BLUE,
            "MATCH": Colors.ORANGE,
            "FILL_BLANK": Colors.TEAL,
            "TAP_COMPLETE": Colors.PINK,
            "SELECT": Colors.CYAN,
            "SKIP": Colors.GRAY,
        }
        color = type_colors.get(ctype_upper, Colors.WHITE)
        type_tag = f"{color}{Colors.BOLD}[{ctype_upper}]{Colors.RESET}"
        counter = f"{Colors.GRAY}#{self._challenge_in_lesson}{Colors.RESET}"
        self._print(f" {Symbols.TARGET} ", Colors.MAGENTA, f"{counter} {type_tag} {question}")

    def answer(self, answer_text):
        """Log the AI's answer."""
        self._print(f" {Symbols.ARROW_LEFT}{Symbols.ARROW_LEFT} ", Colors.GREEN,
                     f"Answer: {Colors.BOLD}{Colors.BRIGHT_GREEN}{answer_text}{Colors.RESET}",
                     f"{Colors.GREEN}{Symbols.BOLT}{Colors.RESET}")

    def ai_tier(self, tier_name, response_time_ms=None):
        """Log which AI tier is being used."""
        tier_icons = {
            "cache": (f"{Symbols.BOLT}", Colors.GOLD, "Cache Hit"),
            "groq": (f"{Symbols.BRAIN}", Colors.BRIGHT_CYAN, "Groq LLaMA 3.3"),
            "gemini": (f"{Symbols.SPARKLE}", Colors.BLUE, "Gemini Flash"),
            "vision": (f"{Symbols.EYE}", Colors.MAGENTA, "Gemini Vision"),
        }
        icon, color, label = tier_icons.get(tier_name, (Symbols.GEAR, Colors.GRAY, tier_name))
        time_str = f" {Colors.GRAY}({response_time_ms}ms){Colors.RESET}" if response_time_ms else ""
        self._print(" AI ", color, f"{color}{icon} {label}{Colors.RESET}{time_str}")

    # ------------------------------------------------------------------
    # Lesson lifecycle
    # ------------------------------------------------------------------

    def lesson_start(self, lesson_number):
        """Print a visual lesson header."""
        self._current_lesson = lesson_number
        self._challenge_in_lesson = 0
        self._lesson_start = datetime.now()
        width = 52

        print()
        print(f"  {Colors.BRIGHT_GREEN}{Symbols.CORNER_TL}{Symbols.BAR_H * width}{Symbols.CORNER_TR}{Colors.RESET}")
        print(f"  {Colors.BRIGHT_GREEN}{Symbols.BAR_V}{Colors.RESET}  {Symbols.OWL}  {Colors.BOLD}{Colors.BRIGHT_GREEN}LESSON {lesson_number}{Colors.RESET}{'':>{width - 14}}{Colors.BRIGHT_GREEN}{Symbols.BAR_V}{Colors.RESET}")
        print(f"  {Colors.BRIGHT_GREEN}{Symbols.BAR_V}{Colors.RESET}  {Colors.GRAY}Started at {self._timestamp()}{Colors.RESET}{'':>{width - 23}}{Colors.BRIGHT_GREEN}{Symbols.BAR_V}{Colors.RESET}")
        print(f"  {Colors.BRIGHT_GREEN}{Symbols.CORNER_BL}{Symbols.BAR_H * width}{Symbols.CORNER_BR}{Colors.RESET}")
        print()

    def lesson_complete_celebration(self, lesson_number):
        """Print a celebration on lesson completion."""
        elapsed = ""
        if self._lesson_start:
            delta = datetime.now() - self._lesson_start
            elapsed = f" in {int(delta.total_seconds())}s"

        print()
        print(f"  {Colors.GOLD}{Symbols.SPARKLE}{Colors.GREEN}{Symbols.SPARKLE}{Colors.CYAN}{Symbols.SPARKLE}  "
              f"{Colors.BOLD}{Colors.BRIGHT_GREEN}LESSON {lesson_number} COMPLETE!{Colors.RESET}  "
              f"{Colors.CYAN}{Symbols.SPARKLE}{Colors.GREEN}{Symbols.SPARKLE}{Colors.GOLD}{Symbols.SPARKLE}")
        print(f"  {Colors.GRAY}   {Symbols.TROPHY} {self._challenge_in_lesson} challenges solved{elapsed}  {Symbols.PARTY}{Colors.RESET}")
        print()

    # ------------------------------------------------------------------
    # Statistics tracking
    # ------------------------------------------------------------------

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

    def track_challenge_type(self, challenge_type):
        """Track per-challenge-type statistics."""
        if challenge_type not in self._challenge_types:
            self._challenge_types[challenge_type] = {"solved": 0, "failed": 0}

    def track_type_result(self, challenge_type, success):
        """Record a result for a specific challenge type."""
        if challenge_type not in self._challenge_types:
            self._challenge_types[challenge_type] = {"solved": 0, "failed": 0}
        if success:
            self._challenge_types[challenge_type]["solved"] += 1
        else:
            self._challenge_types[challenge_type]["failed"] += 1

    # ------------------------------------------------------------------
    # Visual progress bar
    # ------------------------------------------------------------------

    def progress_bar(self, current, total, label="Progress", width=30):
        """Render an inline progress bar."""
        if total <= 0:
            return
        ratio = min(current / total, 1.0)
        filled = int(width * ratio)
        empty = width - filled

        bar = (f"{Colors.BRIGHT_GREEN}{Symbols.BLOCK_FULL * filled}"
               f"{Colors.GRAY}{Symbols.BLOCK_LOW * empty}{Colors.RESET}")
        pct = f"{ratio * 100:.0f}%"
        print(f"  {Colors.GRAY}{label}{Colors.RESET}  {bar}  {Colors.BOLD}{pct}{Colors.RESET}  ({current}/{total})")
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Spinner for async operations
    # ------------------------------------------------------------------

    def start_spinner(self, message="Thinking..."):
        """Start a spinner animation in a background thread."""
        self._spinner_active = True
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

        def spin():
            i = 0
            while self._spinner_active:
                frame = frames[i % len(frames)]
                print(f"\r  {Colors.CYAN}{frame}{Colors.RESET} {Colors.DIM}{message}{Colors.RESET}  ", end="", flush=True)
                time.sleep(0.08)
                i += 1
            print(f"\r{'':>60}\r", end="", flush=True)

        self._spinner_thread = threading.Thread(target=spin, daemon=True)
        self._spinner_thread.start()

    def stop_spinner(self):
        """Stop the spinner animation."""
        self._spinner_active = False
        if self._spinner_thread:
            self._spinner_thread.join(timeout=0.5)
            self._spinner_thread = None

    # ------------------------------------------------------------------
    # Session statistics dashboard
    # ------------------------------------------------------------------

    def print_stats(self):
        """Print a rich visual session statistics dashboard."""
        s = self.stats
        total = s["solved"] + s["failed"] + s["skipped"]
        accuracy = (s["solved"] / total * 100) if total > 0 else 0
        elapsed = self._elapsed()

        # Accuracy color
        if accuracy >= 80:
            acc_color = Colors.BRIGHT_GREEN
            rating = f"{Symbols.STAR} Excellent"
        elif accuracy >= 60:
            acc_color = Colors.GREEN
            rating = f"{Symbols.CHECK} Good"
        elif accuracy >= 40:
            acc_color = Colors.YELLOW
            rating = f"{Symbols.WARNING} Fair"
        else:
            acc_color = Colors.RED
            rating = f"{Symbols.CROSS} Needs work"

        # Accuracy bar
        bar_width = 30
        filled = int(bar_width * accuracy / 100) if total > 0 else 0
        empty = bar_width - filled
        acc_bar = f"{acc_color}{Symbols.BLOCK_FULL * filled}{Colors.GRAY}{Symbols.BLOCK_LOW * empty}{Colors.RESET}"

        W = 54  # inner width

        print()
        print(f"  {Colors.CYAN}{Symbols.CORNER_TL}{Symbols.BAR_H * W}{Symbols.CORNER_TR}{Colors.RESET}")
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Symbols.CHART}  {Colors.BOLD}{Colors.BRIGHT_CYAN}SESSION STATISTICS{Colors.RESET}{'':>{W - 23}}{Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")
        print(f"  {Colors.CYAN}{Symbols.TEE_L}{Symbols.BAR_H * W}{Symbols.TEE_R}{Colors.RESET}")

        # Session duration
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Symbols.CLOCK}  Duration          {Colors.BOLD}{elapsed:>{W - 26}}{Colors.RESET}  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")

        # Lessons
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Symbols.OWL}  Lessons Completed {Colors.BOLD}{Colors.BRIGHT_GREEN}{s['lessons_completed']:>{W - 26}}{Colors.RESET}  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")

        print(f"  {Colors.CYAN}{Symbols.TEE_L}{Symbols.BAR_H * W}{Symbols.TEE_R}{Colors.RESET}")

        # Challenges breakdown
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Colors.GREEN}{Symbols.CHECK}  Solved{Colors.RESET}{'':>{W - 36}}{Colors.BOLD}{Colors.GREEN}{s['solved']:>4}{Colors.RESET}          {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Colors.RED}{Symbols.CROSS}  Failed{Colors.RESET}{'':>{W - 36}}{Colors.BOLD}{Colors.RED}{s['failed']:>4}{Colors.RESET}          {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Colors.YELLOW}{Symbols.WARNING}  Skipped{Colors.RESET}{'':>{W - 37}}{Colors.BOLD}{Colors.YELLOW}{s['skipped']:>4}{Colors.RESET}          {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")

        print(f"  {Colors.CYAN}{Symbols.TEE_L}{Symbols.BAR_H * W}{Symbols.TEE_R}{Colors.RESET}")

        # Accuracy with bar
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Symbols.TARGET}  Accuracy  {acc_bar} {acc_color}{Colors.BOLD}{accuracy:.1f}%{Colors.RESET}  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")
        print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {'':>4}  Rating   {acc_color}{Colors.BOLD}{rating}{Colors.RESET}{'':>{W - 24 - len(rating)}}{Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")

        # Per-type breakdown if available
        if self._challenge_types:
            print(f"  {Colors.CYAN}{Symbols.TEE_L}{Symbols.BAR_H * W}{Symbols.TEE_R}{Colors.RESET}")
            print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}  {Symbols.MAGNIFY}  {Colors.DIM}Challenge Type Breakdown:{Colors.RESET}{'':>{W - 33}}{Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")
            for ctype, counts in self._challenge_types.items():
                ct = counts['solved'] + counts['failed']
                ct_acc = (counts['solved'] / ct * 100) if ct > 0 else 0
                ct_color = Colors.GREEN if ct_acc >= 70 else Colors.YELLOW if ct_acc >= 40 else Colors.RED
                label = ctype.upper()[:12].ljust(12)
                print(f"  {Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}      {Colors.DIM}{label}{Colors.RESET}  {ct_color}{counts['solved']}{Colors.RESET}/{ct}  ({ct_color}{ct_acc:.0f}%{Colors.RESET}){'':>{W - 34 - len(str(counts['solved'])) - len(str(ct))}}{Colors.CYAN}{Symbols.BAR_V}{Colors.RESET}")

        print(f"  {Colors.CYAN}{Symbols.CORNER_BL}{Symbols.BAR_H * W}{Symbols.CORNER_BR}{Colors.RESET}")
        print()

    # ------------------------------------------------------------------
    # Startup banner
    # ------------------------------------------------------------------

    def banner(self):
        """Print the startup banner with ASCII art and gradient colors."""
        g = [Colors.G1, Colors.G2, Colors.G3, Colors.G4, Colors.G5, Colors.G6, Colors.G7, Colors.G8]

        owl_art = [
            f"              {g[2]},___,{Colors.RESET}",
            f"              {g[3]}[O.o]{Colors.RESET}",
            f"              {g[4]}/)__){Colors.RESET}",
            f"              {g[5]}-\"--\"-{Colors.RESET}",
        ]

        title_lines = [
            f"  {g[4]}██████{g[5]}╗ {g[4]}██{g[5]}╗   {g[4]}██{g[5]}╗ {g[4]}██████{g[5]}╗ {g[4]}██{g[5]}╗     {g[4]}██{g[5]}╗{g[4]}███{g[5]}╗  {g[4]}██{g[5]}╗ {g[4]}██████{g[5]}╗  {g[4]}██████{g[5]}╗{Colors.RESET}",
            f"  {g[4]}██{g[5]}╔══{g[4]}██{g[5]}╗{g[4]}██{g[5]}║   {g[4]}██{g[5]}║{g[4]}██{g[5]}╔═══{g[4]}██{g[5]}╗{g[4]}██{g[5]}║     {g[4]}██{g[5]}║{g[4]}████{g[5]}╗ {g[4]}██{g[5]}║{g[4]}██{g[5]}╔════╝ {g[4]}██{g[5]}╔═══{g[4]}██{g[5]}╗{Colors.RESET}",
            f"  {g[5]}██{g[6]}║  {g[5]}██{g[6]}║{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{g[5]}██{g[6]}║     {g[5]}██{g[6]}║{g[5]}██{g[6]}╔{g[5]}██{g[6]}╗{g[5]}██{g[6]}║{g[5]}██{g[6]}║  {g[5]}███{g[6]}╗{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{Colors.RESET}",
            f"  {g[5]}██{g[6]}║  {g[5]}██{g[6]}║{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{g[5]}██{g[6]}║     {g[5]}██{g[6]}║{g[5]}██{g[6]}║╚{g[5]}████{g[6]}║{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{g[5]}██{g[6]}║   {g[5]}██{g[6]}║{Colors.RESET}",
            f"  {g[6]}██████{g[7]}╔╝╚{g[6]}██████{g[7]}╔╝╚{g[6]}██████{g[7]}╔╝{g[6]}███████{g[7]}╗{g[6]}██{g[7]}║{g[6]}██{g[7]}║ ╚{g[6]}███{g[7]}║╚{g[6]}██████{g[7]}╔╝╚{g[6]}██████{g[7]}╔╝{Colors.RESET}",
            f"  {g[2]}╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚═╝╚═╝  ╚══╝ ╚═════╝  ╚═════╝{Colors.RESET}",
        ]

        subtitle = f"  {Colors.BRIGHT_GREEN}{Symbols.BOLT} AI-Powered Autonomous Language Learning Agent{Colors.RESET}"
        version_line = f"  {Colors.GRAY}v2.0.0 {Symbols.BAR_V} {Symbols.OWL} Duolingo Agent {Symbols.BAR_V} {Symbols.ROCKET} Ready to learn{Colors.RESET}"

        W = 72
        border_color = Colors.G4

        print()
        print(f"  {border_color}{Symbols.CORNER_TL}{Symbols.BAR_H * W}{Symbols.CORNER_TR}{Colors.RESET}")

        # Owl art
        for line in owl_art:
            print(f"  {border_color}{Symbols.BAR_V}{Colors.RESET}{line:>{W - 2}}  {border_color}{Symbols.BAR_V}{Colors.RESET}")

        print(f"  {border_color}{Symbols.BAR_V}{' ' * W}{Symbols.BAR_V}{Colors.RESET}")

        # Title
        for line in title_lines:
            print(f"  {border_color}{Symbols.BAR_V}{Colors.RESET} {line}")

        print(f"  {border_color}{Symbols.BAR_V}{' ' * W}{Symbols.BAR_V}{Colors.RESET}")

        # Subtitle
        print(f"  {border_color}{Symbols.BAR_V}{Colors.RESET}{subtitle}")
        print(f"  {border_color}{Symbols.BAR_V}{Colors.RESET}{version_line}")
        print(f"  {border_color}{Symbols.BAR_V}{' ' * W}{Symbols.BAR_V}{Colors.RESET}")

        print(f"  {border_color}{Symbols.CORNER_BL}{Symbols.BAR_H * W}{Symbols.CORNER_BR}{Colors.RESET}")
        print()

    # ------------------------------------------------------------------
    # Confidence indicators for executor
    # ------------------------------------------------------------------

    def match_confidence(self, match_type, option_text):
        """Log an answer match with confidence indicator."""
        indicators = {
            "exact": (f"{Colors.GREEN}{Symbols.CHECK}{Symbols.CHECK}{Colors.RESET}", "exact match"),
            "substring": (f"{Colors.YELLOW}{Symbols.CHECK}~{Colors.RESET}", "substring"),
            "overlap": (f"{Colors.ORANGE}~{Symbols.CHECK}{Colors.RESET}", "word overlap"),
        }
        icon, label = indicators.get(match_type, (Symbols.GEAR, "unknown"))
        self._print(" ── ", Colors.DIM, f"{icon} Selected ({label}): {Colors.BOLD}{option_text}{Colors.RESET}")
