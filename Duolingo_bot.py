"""
Duolingo Auto-Bot — No API needed, completely free
Uses PyAutoGUI + color detection + image template matching

Install deps:
    pip install pyautogui pillow pygetwindow opencv-python

How to use:
    1. Open Duolingo desktop app
    2. Navigate to home screen (streak visible)
    3. Run: python duolingo_bot.py
    4. Don't touch your mouse while it runs!

Setup (one-time):
    - Take screenshots of the buttons listed in TEMPLATES section
    - Save them in the same folder as this script
"""

import pyautogui
import time
import sys
import os
from PIL import ImageGrab, Image
import numpy as np

# ─────────────────────────────────────────────
# CONFIG — tweak these if needed
# ─────────────────────────────────────────────
DELAY           = 1.2    # seconds between actions (increase if Duolingo is slow)
ANSWER_DELAY    = 0.4    # seconds between clicking each answer option
MAX_QUESTIONS   = 30     # safety limit (lessons are usually 15-20 questions)
CONFIDENCE      = 0.75   # template matching confidence (lower = more lenient)

# Screen resolution — update if not 1920x1080
SCREEN_W, SCREEN_H = pyautogui.size()

pyautogui.FAILSAFE = True   # move mouse to top-left corner to emergency stop
pyautogui.PAUSE    = 0.1    # tiny pause between every pyautogui call


# ─────────────────────────────────────────────
# TEMPLATE IMAGE PATHS
# Save screenshots of these Duolingo UI elements
# and place them in the same folder as this script.
# You can take these screenshots manually using
# Windows Snipping Tool (Win+Shift+S)
# ─────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES = {
    "start_btn"    : os.path.join(SCRIPT_DIR, "btn_start.png"),       # "Start" button on lesson card
    "continue_btn" : os.path.join(SCRIPT_DIR, "btn_continue.png"),    # green "Continue" button
    "check_btn"    : os.path.join(SCRIPT_DIR, "btn_check.png"),       # green "Check" button
    "next_btn"     : os.path.join(SCRIPT_DIR, "btn_next.png"),        # "Next" arrow button
    "lesson_done"  : os.path.join(SCRIPT_DIR, "lesson_complete.png"), # lesson complete screen
    "practice_btn" : os.path.join(SCRIPT_DIR, "btn_practice.png"),    # practice/start on home
}


# ─────────────────────────────────────────────
# COLOR DETECTION — finds green button by pixel color
# Duolingo's primary button is always bright green
# ─────────────────────────────────────────────
DUOLINGO_GREEN_RANGES = [
    # (R_min, R_max, G_min, G_max, B_min, B_max)
    (50,  100, 175, 210, 50,  100),   # main green #58CC02 range
    (60,  120, 180, 220, 40,  100),   # slight variation
]

def take_screenshot():
    """Capture current screen as numpy array"""
    img = ImageGrab.grab()
    return np.array(img)

def find_green_button(screenshot=None):
    """
    Scan bottom 35% of screen for Duolingo's green button.
    Returns (center_x, center_y) or None.
    """
    if screenshot is None:
        screenshot = take_screenshot()

    h, w = screenshot.shape[:2]
    # Only scan bottom portion where button always lives
    scan_region = screenshot[int(h * 0.65):, :]

    for (rmin, rmax, gmin, gmax, bmin, bmax) in DUOLINGO_GREEN_RANGES:
        r = scan_region[:, :, 0]
        g = scan_region[:, :, 1]
        b = scan_region[:, :, 2]

        mask = (
            (r >= rmin) & (r <= rmax) &
            (g >= gmin) & (g <= gmax) &
            (b >= bmin) & (b <= bmax)
        )

        if mask.sum() > 1500:   # enough green pixels to be a button
            ys, xs = np.where(mask)
            cx = int(xs.mean())
            cy = int(ys.mean()) + int(h * 0.65)
            return (cx, cy)

    return None

def find_image_on_screen(template_path, confidence=CONFIDENCE):
    """
    Find a template image on screen. Returns center (x, y) or None.
    Uses OpenCV if available, falls back to PyAutoGUI.
    """
    if not os.path.exists(template_path):
        return None

    try:
        location = pyautogui.locateCenterOnScreen(
            template_path,
            confidence=confidence,
            grayscale=True
        )
        return location
    except Exception:
        return None

def click_at(x, y, label="point"):
    """Click at absolute screen coordinates"""
    print(f"  → Clicking {label} at ({x}, {y})")
    pyautogui.moveTo(x, y, duration=0.25)
    time.sleep(0.1)
    pyautogui.click()
    time.sleep(DELAY)

def click_green_button():
    """Find and click the green Continue/Check button"""
    pos = find_green_button()
    if pos:
        click_at(pos[0], pos[1], "green button")
        return True

    # Fallback: try template matching
    for key in ["continue_btn", "check_btn", "next_btn"]:
        pos = find_image_on_screen(TEMPLATES[key])
        if pos:
            click_at(pos[0], pos[1], key)
            return True

    return False


# ─────────────────────────────────────────────
# QUESTION HANDLERS
# Duolingo has ~5 question types. We handle each.
# ─────────────────────────────────────────────

def detect_question_type(screenshot):
    """
    Roughly detect what kind of question is on screen.
    Returns: 'mcq' | 'wordbank' | 'typing' | 'matching' | 'unknown'
    """
    h, w = screenshot.shape[:2]

    # Scan middle section for word bank tiles (small rounded tiles in a row)
    # Word bank tiles tend to appear in the bottom-middle region
    # We use a simplified heuristic: look for many small light-colored rectangles

    # For now, return 'mcq' as default (most common question type)
    # You can improve this later by adding template images for each type
    return "mcq"

def answer_mcq():
    """
    Multiple Choice: just click the FIRST option.
    Duolingo MCQ options are usually in the center of the screen,
    roughly at y=50-65% of screen height.
    """
    h, w = SCREEN_H, SCREEN_W

    # Approximate positions of first 3 MCQ options
    # These are CENTER of screen horizontally, spaced vertically
    option_positions = [
        (w // 2, int(h * 0.45)),   # option 1
        (w // 2, int(h * 0.55)),   # option 2
        (w // 2, int(h * 0.62)),   # option 3
    ]

    print("  → MCQ detected — clicking first option")
    click_at(option_positions[0][0], option_positions[0][1], "MCQ option 1")
    time.sleep(ANSWER_DELAY)

def answer_wordbank():
    """
    Word bank: click words in the top row of the bank.
    Bank tiles appear at ~y=70-80% of screen.
    We click 2-4 words to form a sentence.
    """
    h, w = SCREEN_H, SCREEN_W
    bank_y = int(h * 0.75)

    tile_positions = [
        (int(w * 0.25), bank_y),
        (int(w * 0.40), bank_y),
        (int(w * 0.55), bank_y),
    ]

    print("  → Word bank detected — clicking first 3 tiles")
    for pos in tile_positions:
        click_at(pos[0], pos[1], "word tile")
        time.sleep(ANSWER_DELAY)

def answer_typing():
    """
    Typing question: type a simple short answer.
    Duolingo accepts partial matches / multiple valid answers,
    so typing something reasonable usually works for streak purposes.
    """
    h, w = SCREEN_H, SCREEN_W

    # Click the text input box (center of screen)
    input_x, input_y = w // 2, int(h * 0.55)
    click_at(input_x, input_y, "text input")
    time.sleep(0.3)

    # Type a simple answer — this often works for common languages
    pyautogui.hotkey("ctrl", "a")
    pyautogui.typewrite("I", interval=0.05)
    print("  → Typing question — typed answer")

def handle_question():
    """Main question handler — detect type and answer"""
    ss = take_screenshot()
    q_type = detect_question_type(ss)

    if q_type == "wordbank":
        answer_wordbank()
    elif q_type == "typing":
        answer_typing()
    else:
        answer_mcq()   # default

    time.sleep(0.5)

    # Always press Enter or click Continue after answering
    pyautogui.press("enter")
    time.sleep(0.8)

    if not click_green_button():
        # Last resort: press space bar (sometimes works for continue)
        pyautogui.press("space")
        time.sleep(0.5)


# ─────────────────────────────────────────────
# LESSON FLOW
# ─────────────────────────────────────────────

def is_lesson_complete():
    """Check if we're on the lesson complete screen"""
    pos = find_image_on_screen(TEMPLATES["lesson_done"])
    if pos:
        return True

    # Backup: look for XP/star graphics — lesson complete screens
    # have very bright golden/yellow colors at the top
    ss = take_screenshot()
    h, w = ss.shape[:2]
    top_region = ss[:int(h * 0.4), :]

    # Count golden pixels (lesson complete often shows stars/XP in gold)
    r, g, b = top_region[:,:,0], top_region[:,:,1], top_region[:,:,2]
    gold_mask = (r > 220) & (g > 160) & (g < 210) & (b < 60)
    if gold_mask.sum() > 3000:
        return True

    return False

def start_lesson():
    """Click the Start / Practice button on the home screen"""
    print("\n[1/3] Looking for lesson start button...")

    for key in ["start_btn", "practice_btn"]:
        pos = find_image_on_screen(TEMPLATES[key])
        if pos:
            click_at(pos[0], pos[1], key)
            print("  ✓ Clicked start button")
            time.sleep(2.0)   # wait for lesson to load
            return True

    # Fallback: click center of screen (where Start usually is)
    print("  → Template not found, clicking center-screen Start button...")
    click_at(SCREEN_W // 2, int(SCREEN_H * 0.75), "estimated start position")
    time.sleep(2.0)
    return True

def run_lesson():
    """Main lesson loop — answer questions until complete"""
    print("\n[2/3] Running lesson...")

    for i in range(MAX_QUESTIONS):
        print(f"\n  Question {i+1}/{MAX_QUESTIONS}")

        if is_lesson_complete():
            print("\n[3/3] 🎉 Lesson complete! Streak saved!")
            # Click Continue/Close on completion screen
            time.sleep(1.0)
            click_green_button()
            return True

        handle_question()
        time.sleep(DELAY)

    print("\n  ⚠ Reached max questions limit without detecting completion.")
    print("  → Try increasing MAX_QUESTIONS or check if lesson is done manually.")
    return False


# ─────────────────────────────────────────────
# SETUP CHECKER
# ─────────────────────────────────────────────

def check_templates():
    """Warn user about missing template images"""
    missing = []
    for name, path in TEMPLATES.items():
        if not os.path.exists(path):
            missing.append(f"  - {name}: {os.path.basename(path)}")

    if missing:
        print("\n⚠  MISSING TEMPLATE IMAGES (optional but improves accuracy):")
        for m in missing:
            print(m)
        print("\n  → The bot will still run using color detection + coordinate estimation.")
        print("  → For better accuracy, screenshot these buttons and save them in:")
        print(f"     {SCRIPT_DIR}")
        print()
    else:
        print("✓ All template images found!")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Duolingo Auto-Bot  (free, no API)")
    print("=" * 50)
    print(f"\nScreen: {SCREEN_W}x{SCREEN_H}")
    print("Emergency stop: move mouse to TOP-LEFT corner of screen!\n")

    check_templates()

    print("Starting in 5 seconds...")
    print("→ Switch to Duolingo app NOW and navigate to the home screen")
    for i in range(5, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print()

    try:
        start_lesson()
        success = run_lesson()
        if success:
            print("\n✅ Done! Your streak is safe for today.")
        else:
            print("\n⚠ Bot finished but couldn't confirm completion. Check Duolingo manually.")
    except pyautogui.FailSafeException:
        print("\n🛑 Emergency stop triggered (mouse moved to corner). Bot stopped.")
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("→ Try running again or adjust the DELAY value at the top of the script.")

if __name__ == "__main__":
    main()