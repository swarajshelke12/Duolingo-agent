import os
import time
import random
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import google.generativeai as genai

class DuolingoAgent:
    def __init__(self, api_key=None, headless=False, browser_path=None):
        # Load from config if exists
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
        
        self.api_key = api_key or self.config.get("api_key")
        self.browser_path = browser_path or self.config.get("browser_path")
        self.headless = headless or self.config.get("headless", False)

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        self.options = Options()
        if self.headless:
            self.options.add_argument("--headless")
        
        if self.browser_path and os.path.exists(self.browser_path):
            self.options.binary_location = self.browser_path
            self.log(f"Using custom browser: {self.browser_path}")

        self.options.add_argument("--log-level=3")
        self.options.add_argument("--mute-audio")
        self.options.add_argument("--disable-notifications")
        self.options.add_argument("--window-size=1280,720")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.options)
        self.wait = WebDriverWait(self.driver, 15)

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {}

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def log(self, message):
        print(f"[DuolingoAgent] {message}")

    def is_logged_in(self):
        try:
            self.driver.get("https://www.duolingo.com/learn")
            time.sleep(3)
            return "learn" in self.driver.current_url
        except:
            return False

    def wait_for_login(self):
        self.log("Waiting for user to login...")
        self.driver.get("https://www.duolingo.com/?is_login=true")
        while "learn" not in self.driver.current_url:
            time.sleep(1)
        self.log("Login detected!")

    def start_lesson(self):
        try:
            # Find the start button on the learn page
            # Based on subagent analysis: button[class*="_1gEmM"] or containing 'Start'
            selectors = [
                "button[data-test='start-button']",
                "button[class*='_1gEmM']",
                "//button[contains(text(), 'Start')]",
                "//button[contains(text(), 'Practice')]"
            ]
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        start_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        start_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    start_btn.click()
                    self.log(f"Clicked Start button using {selector}")
                    time.sleep(2)
                    return True
                except:
                    continue
            self.log("Could not find start button with standard selectors.")
            return False
        except Exception as e:
            self.log(f"Error in start_lesson: {e}")
            return False

    def get_challenge_data(self):
        """Extracts question and options from the current challenge"""
        try:
            # Question text
            try:
                question_header = self.driver.find_element(By.CSS_SELECTOR, "h1[data-test='challenge-header'], [data-test='challenge-header']").text
            except:
                question_header = "Translate this sentence" # Fallback

            # Sub-question / Prompt
            try:
                sub_question = self.driver.find_element(By.CSS_SELECTOR, "[data-test='challenge-secondary-prompt'], [data-test='hint-sentence']").text
            except:
                sub_question = ""

            # Options (MCQ or Fill in the blanks)
            options = []
            option_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='challenge-choice'], [role='radio'], button[class*='_3fmUm']")
            for opt in option_elements:
                if opt.text:
                    options.append(opt.text)

            # Word Bank Tiles
            tiles = []
            tile_elements = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test='word-bank-tile']")
            for tile in tile_elements:
                if tile.text and tile.is_enabled():
                    tiles.append(tile.text)

            return {
                "header": question_header,
                "prompt": sub_question,
                "options": options,
                "tiles": tiles,
                "type": "mcq" if options else ("wordbank" if tiles else "typing")
            }
        except Exception as e:
            # self.log(f"Error extracting challenge data: {e}")
            return None

    def solve_with_ai(self, data):
        if not self.api_key:
            return None
            
        prompt = f"""
        You are a Duolingo expert. Solve the following language challenge.
        Question: {data['header']}
        Prompt: {data['prompt']}
        Options: {data['options']}
        Word Bank: {data['tiles']}
        
        Instructions:
        - If it's MCQ, return the EXACT text of the correct option.
        - If it's Word Bank, return the tiles in the correct order, comma-separated.
        - If it's Typing, return the correct translation.
        
        Return ONLY the answer.
        """
        
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def run_automation(self):
        self.log("Starting automation loop...")
        while True:
            try:
                # Check for lesson completion / XP screens
                if "learn" in self.driver.current_url or "xp-summary" in self.driver.current_url:
                    self.log("Lesson completed or on learn page.")
                    # Try to click any final continue button
                    try:
                        final_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                        final_btn.click()
                        time.sleep(2)
                    except:
                        break
                    if "learn" in self.driver.current_url:
                        break
                
                # Check for "Check", "Continue", "Next", "Got it" buttons
                try:
                    next_selectors = [
                        "button[data-test='player-next']",
                        "//button[contains(text(), 'Continue')]",
                        "//button[contains(text(), 'Check')]",
                        "//button[contains(text(), 'Next')]",
                        "//button[contains(text(), 'Got it')]"
                    ]
                    btn_clicked = False
                    for sel in next_selectors:
                        try:
                            if sel.startswith("//"):
                                btn = self.driver.find_element(By.XPATH, sel)
                            else:
                                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                            
                            if btn.is_displayed() and btn.is_enabled():
                                # Only click if it's "Continue" or if we've already answered
                                btn_text = btn.text.lower()
                                if "continue" in btn_text or "next" in btn_text or "got it" in btn_text:
                                    btn.click()
                                    self.log(f"Clicked {btn_text}")
                                    btn_clicked = True
                                    time.sleep(1)
                                    break
                        except:
                            continue
                    if btn_clicked: continue
                except:
                    pass

                # Handle Challenge
                data = self.get_challenge_data()
                if data and data['header']:
                    self.log(f"Challenge: {data['header']}")
                    answer = self.solve_with_ai(data)
                    self.log(f"AI Answer: {answer}")
                    
                    if data['type'] == "mcq":
                        # Find and click the option with matching text
                        clicked = False
                        option_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='challenge-choice'], [role='radio'], button[class*='_3fmUm']")
                        for opt_elem in option_elements:
                            if answer.lower() in opt_elem.text.lower() or opt_elem.text.lower() in answer.lower():
                                opt_elem.click()
                                clicked = True
                                break
                        if not clicked and option_elements:
                            option_elements[0].click() # Fallback to first if AI fails
                    
                    elif data['type'] == "wordbank":
                        # Click tiles in order
                        # AI might return comma-separated or space-separated
                        answer_tiles = [a.strip().lower() for a in answer.replace(',', ' ').split()]
                        for a_tile in answer_tiles:
                            tile_elements = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test='word-bank-tile']")
                            for t_elem in tile_elements:
                                if t_elem.text.lower() == a_tile and t_elem.is_enabled() and "_1yW_Y" not in t_elem.get_attribute("class"):
                                    # _1yW_Y is often the 'used' class
                                    t_elem.click()
                                    time.sleep(0.3)
                                    break
                    
                    elif data['type'] == "typing":
                        try:
                            input_box = self.driver.find_element(By.CSS_SELECTOR, "textarea[data-test='challenge-translate-input'], input[data-test='challenge-text-input']")
                            input_box.send_keys(answer)
                        except:
                            pass

                    # Click Check
                    time.sleep(0.5)
                    try:
                        check_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Check')] | //button[@data-test='player-next']")
                        check_btn.click()
                    except:
                        pass
                
                time.sleep(2)
            except Exception as e:
                # self.log(f"Loop error: {e}")
                time.sleep(2)

if __name__ == "__main__":
    # Test run
    agent = DuolingoAgent()
    agent.wait_for_login()
    agent.start_lesson()
    # agent.run_automation()
