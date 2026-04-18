import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from google import genai
from groq import Groq
class DuolingoAgent:
    def __init__(self, api_key=None, groq_api_key=None, headless=False, browser_path=None):
        self.api_key = api_key
        self.groq_api_key = groq_api_key
        self.browser_path = browser_path
        self.headless = headless

        if self.groq_api_key:
            self.groq_client = Groq(api_key=self.groq_api_key)
        else:
            self.groq_client = None

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
        
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
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--remote-debugging-port=9222")
        self.options.add_argument("--disable-gpu")
        
        # Anti-detection & Persistent Profile
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        
        profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")
        self.options.add_argument(f"user-data-dir={profile_path}")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.options)
        self.wait = WebDriverWait(self.driver, 15)

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
        while not any(keyword in self.driver.current_url for keyword in ["learn", "lesson", "practice"]):
            time.sleep(1)
        self.log("Login detected!")

    def start_lesson(self):
        try:
            # Check if already in a lesson
            if "lesson" in self.driver.current_url or "practice" in self.driver.current_url:
                self.log("Already in a lesson.")
                return True

            self.log("Trying to find a lesson to start...")
            selectors = [
                "a[data-test='practice-hub-nav']",
                "button[data-test='start-button']",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'practice')]",
                "//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]",
                "//div[@role='button']"
            ]
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        elem = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        elem = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    
                    if elem.is_displayed():
                        elem.click()
                        self.log(f"Clicked Start using {selector}")
                        time.sleep(2)
                        
                        # Sometimes we click a node and another start button pops up
                        try:
                            start_popup = self.driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]")
                            start_popup.click()
                            time.sleep(2)
                        except:
                            pass
                            
                        return True
                except:
                    continue
            
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
            tile_elements = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test='word-bank-tile'], [data-test='challenge-tap-token']")
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
        - If it's MCQ, return ONLY the EXACT text of the correct option.
        - If it's Word Bank, return the tiles in the correct order, separated by a single space.
        - If it's a Matching exercise (pairs), return the pairs sequentially (word1 translation1 word2 translation2).
        - If it's Typing, return the correct translation.
        
        Return ONLY the answer text, no conversational filler, no labels.
        """
        
        
        if self.groq_client:
            # Try Groq API first
            try:
                try:
                    completion = self.groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="openai/gpt-oss-20b",
                        temperature=1,
                        max_completion_tokens=500,
                        top_p=1,
                        reasoning_effort="medium",
                        stream=True,
                        stop=None
                    )
                    
                    answer_text = ""
                    for chunk in completion:
                        content = chunk.choices[0].delta.content or ""
                        answer_text += content
                    
                    return answer_text.strip()
                except Exception as inner_e:
                    if "not found" in str(inner_e).lower() or "invalid" in str(inner_e).lower():
                        self.log("Requested model not found, falling back to llama-3.3-70b-versatile...")
                        chat_completion = self.groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile"
                        )
                        return chat_completion.choices[0].message.content.strip()
                    else:
                        raise inner_e
            except Exception as e:
                error_str = str(e)
                self.log(f"Primary API Error: {error_str}. Falling back to Gemini...")
                if "429" in error_str:
                    time.sleep(2)
        
        if self.client:
            # Fallback to Gemini
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                return response.text.strip()
            except Exception as e:
                error_str = str(e)
                self.log(f"Gemini API Error: {error_str}")
                if "429" in error_str:
                    self.log("Rate limit hit! Pausing for 15 seconds to let API recover...")
                    time.sleep(15)
                return None
                
        return None

    def run_automation(self):
        self.log("Starting automation loop...")
        last_prompt = None
        last_answer = None
        
        while True:
            try:
                if "learn" in self.driver.current_url:
                    self.log("Returned to the learn page. Lesson must be complete.")
                    break
                
                if "xp-summary" in self.driver.current_url:
                    self.log("On XP summary screen.")
                    try:
                        final_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Continue')]")
                        final_btn.click()
                        time.sleep(0.5)
                    except:
                        pass
                
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
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    self.log(f"Clicked {btn_text}")
                                    btn_clicked = True
                                    time.sleep(0.3)
                                    break
                        except:
                            continue
                    if btn_clicked: continue
                except:
                    pass

                # Handle Challenge
                data = self.get_challenge_data()
                if data and data['header']:
                    current_prompt = data.get('prompt', '')
                    
                    if current_prompt != last_prompt or not last_answer:
                        self.log(f"Challenge: {data['header']}")
                        answer = self.solve_with_ai(data)
                        if answer:
                            self.log(f"AI Answer: {answer}")
                            last_prompt = current_prompt
                            last_answer = answer
                        else:
                            last_answer = None
                    else:
                        # Use cached answer
                        answer = last_answer
                    
                    if not answer:
                        time.sleep(1)
                        continue
                        
                    if data['type'] == "mcq":
                        # Find and click the option with matching text
                        clicked = False
                        option_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='challenge-choice'], [role='radio'], button[class*='_3fmUm']")
                        for opt_elem in option_elements:
                            opt_text = opt_elem.text.lower().strip()
                            if len(opt_text) > 0 and (opt_text in answer.lower() or answer.lower() in opt_text):
                                self.driver.execute_script("arguments[0].click();", opt_elem)
                                clicked = True
                                break
                        if not clicked and option_elements:
                            self.driver.execute_script("arguments[0].click();", option_elements[0]) # Fallback to first if AI fails
                    
                    elif data['type'] == "wordbank":
                        import re
                        answer_clean = re.sub(r'[^\w\s]', '', answer).lower()
                        answer_tiles = answer_clean.split()
                        
                        clicked_elements = set()
                        for a_tile in answer_tiles:
                            tile_elements = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test='word-bank-tile'], [data-test='challenge-tap-token']")
                            for t_elem in tile_elements:
                                if t_elem not in clicked_elements and t_elem.text.lower() == a_tile and t_elem.is_enabled() and "_1yW_Y" not in t_elem.get_attribute("class"):
                                    self.driver.execute_script("arguments[0].click();", t_elem)
                                    clicked_elements.add(t_elem)
                                    time.sleep(0.1)
                                    break
                    
                    elif data['type'] == "typing":
                        try:
                            input_box = self.driver.find_element(By.CSS_SELECTOR, "textarea[data-test='challenge-translate-input'], input[data-test='challenge-text-input']")
                            input_box.send_keys(answer)
                        except:
                            pass

                    # Click Check
                    time.sleep(0.2)
                    try:
                        check_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Check')] | //button[@data-test='player-next']")
                        self.driver.execute_script("arguments[0].click();", check_btn)
                    except:
                        pass
                
                time.sleep(0.5)
            except Exception as e:
                self.log(f"Loop error: {e}")
                time.sleep(0.5)

if __name__ == "__main__":
    print("="*50)
    print(" Duolingo AI Agent (Fast Mode)")
    print("="*50)
    
    # Load environment variables from .env file securely
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val
                    
    api_key = os.environ.get("GEMINI_API_KEY")
    groq_api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key and not groq_api_key:
        print("Error: A Gemini or Groq API key is required. Please add them to your .env file.")
        exit(1)
        
    agent = DuolingoAgent(api_key=api_key, groq_api_key=groq_api_key)
    agent.wait_for_login()
    
    while True:
        if any(keyword in agent.driver.current_url for keyword in ["lesson", "practice"]):
            agent.log("Lesson detected! Taking over...")
            agent.run_automation()
        else:
            agent.log("Waiting for a lesson to start... (Please click a lesson manually in the browser)")
            time.sleep(3)
