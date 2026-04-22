import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
                "//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]"
            ]
            
            clicked = False
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                            time.sleep(0.5)
                            self.driver.execute_script("arguments[0].click();", elem)
                            self.log(f"Clicked Start using {selector}")
                            time.sleep(2)
                            clicked = True
                            break
                    if clicked:
                        break
                except:
                    continue
            
            if clicked:
                # Sometimes we click a node and another start button pops up
                try:
                    start_popup = self.driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]")
                    for p in start_popup:
                        if p.is_displayed():
                            self.driver.execute_script("arguments[0].click();", p)
                            time.sleep(2)
                            break
                except:
                    pass
                return True
                
            # Fallback: try to click skill nodes
            try:
                nodes = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
                for n in nodes:
                    if n.is_displayed():
                        self.driver.execute_script("arguments[0].click();", n)
                        time.sleep(0.5)
                        
                        start_popup = self.driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]")
                        for p in start_popup:
                            if p.is_displayed():
                                self.driver.execute_script("arguments[0].click();", p)
                                time.sleep(2)
                                return True
            except:
                pass
                
            return False
        except Exception as e:
            self.log(f"Error in start_lesson: {e}")
            return False

    def get_challenge_data(self):
        """Extracts question and options from the current challenge"""
        try:
            # Detect Challenge Type
            challenge_type = "unknown"
            try:
                challenge_node = self.driver.find_element(By.CSS_SELECTOR, "[data-test^='challenge challenge-']")
                c_type_raw = challenge_node.get_attribute("data-test")
                challenge_type = c_type_raw.split(" ")[1].replace("challenge-", "")
            except:
                pass

            # Question text
            try:
                question_header = self.driver.find_element(By.CSS_SELECTOR, "h1[data-test='challenge-header'], [data-test='challenge-header']").text
            except:
                question_header = ""

            # Sub-question / Prompt
            try:
                sub_question_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-test='challenge-secondary-prompt'], [data-test='hint-sentence'], [dir='ltr'] > span")
                sub_question = " ".join([elem.text for elem in sub_question_elements if elem.text])
            except:
                sub_question = ""

            # Options (MCQ)
            options = []
            option_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='challenge-choice'], [role='radio'], button[data-test='challenge-choice']")
            for opt in option_elements:
                if opt.text:
                    clean_text = opt.text
                    if '\n' in clean_text:
                        clean_text = clean_text.split('\n', 1)[-1]
                    options.append(clean_text)

            # Word Bank Tiles
            tiles = []
            tile_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='word-bank'] button[data-test='challenge-tap-token'], button[data-test='word-bank-tile']")
            for tile in tile_elements:
                if tile.text and tile.is_enabled():
                    tiles.append(tile.text)

            # Match tokens (matching pairs)
            match_tokens = []
            if challenge_type == "match":
                match_elements = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test='challenge-tap-token']")
                for match in match_elements:
                    if match.text and match.is_enabled():
                         match_tokens.append(match.text)
                tiles = [] # Clear tiles so it doesn't get confused with wordbank
                
            # Typing textarea
            is_typing = False
            try:
                typing_box = self.driver.find_element(By.CSS_SELECTOR, "textarea[data-test='challenge-translate-input'], input[data-test='challenge-text-input']")
                if typing_box.is_displayed():
                    is_typing = True
            except:
                pass

            determined_type = "unknown"
            if challenge_type == "match":
                determined_type = "match"
            elif is_typing:
                determined_type = "typing"
            elif tiles:
                determined_type = "wordbank"
            elif options:
                determined_type = "mcq"

            return {
                "header": question_header,
                "prompt": sub_question,
                "options": options,
                "tiles": tiles,
                "match_tokens": match_tokens,
                "type": determined_type,
                "raw_type": challenge_type
            }
        except Exception as e:
            self.log(f"Error extracting challenge data: {e}")
            return None

    def solve_with_ai(self, data):
        if not self.api_key and not self.groq_api_key:
            return None
            
        prompt = f"""
        You are an expert Duolingo solver. Output ONLY valid JSON, with no other text or explanation. 
        Solve the following language challenge with maximum accuracy. CAREFULLY infer the target language and source language based on the words.
        Challenge Type: {data.get('raw_type', 'unknown')}
        Question Header: {data.get('header', '')}
        Prompt/Context: {data.get('prompt', '')}
        Options (MCQ): {data.get('options', [])}
        Word Bank (Tiles): {data.get('tiles', [])}
        Match Tokens: {data.get('match_tokens', [])}
        Determined format: {data.get('type', 'unknown')}
        
        Instructions:
        - If format is 'mcq', the "answer" field should be the EXACT text of the correct option from the Options list.
        - If format is 'wordbank', the "answer" field should be a list of strings. YOU MUST USE EXACTLY THE STRINGS FROM THE PROVIDED 'Word Bank (Tiles)' ARRAY. Do not alter capitalization or punctuation. The strings must perfectly match the elements in the provided tiles list.
        - If format is 'match', the "answer" field should be a list of lists, where each sublist contains the pair of matching tokens (e.g. [["Word1", "Translation1"], ["Word2", "Translation2"]]). Use EXACT tokens from the Match Tokens array.
        - If format is 'typing', the "answer" field should be the correct translated text to be typed.
        
        JSON schema:
        {{
            "answer": <String, or List of Strings, or List of Lists based on format instructions above>
        }}
        """
        
        if self.groq_client:
            # Try Groq API first
            try:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                return chat_completion.choices[0].message.content.strip()
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
        self.log("Starting reliable automation loop...")
        last_prompt = None
        last_answer = None
        consecutive_failures = 0
        
        while True:
            try:
                if "learn" in self.driver.current_url:
                    self.log("Returned to the learn page. Lesson must be complete.")
                    break
                
                if "xp-summary" in self.driver.current_url:
                    self.log("On XP summary screen.")
                    try:
                        final_btn = self.driver.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]")
                        final_btn.click()
                        time.sleep(2)
                    except:
                        pass
                
                # Skip listening/speaking if possible
                try:
                    skip_listen = self.driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'can') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'listen')]")
                    for btn in skip_listen:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.log("Skipped listening challenge.")
                            time.sleep(1)
                            break
                    skip_speak = self.driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'can') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'speak')]")
                    for btn in skip_speak:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            self.log("Skipped speaking challenge.")
                            time.sleep(1)
                            break
                except:
                    pass
                
                # Check for "Check", "Continue", "Next", "Got it" buttons
                try:
                    next_selectors = [
                        "button[data-test='player-next']",
                        "//button[contains(text(), 'Continue')]",
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
                                btn_text = btn.text.lower()
                                if "continue" in btn_text or "next" in btn_text or "got it" in btn_text:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    self.log(f"Clicked {btn_text}")
                                    btn_clicked = True
                                    time.sleep(2) # Add delay for reliability
                                    break
                        except:
                            continue
                    if btn_clicked: continue
                except:
                    pass

                # Handle Challenge
                data = self.get_challenge_data()
                if data and (data.get('header') or data.get('prompt') or data.get('options') or data.get('tiles') or data.get('match_tokens')):
                    current_prompt = data.get('prompt', '') + str(data.get('options', [])) + str(data.get('tiles', []))
                    
                    if current_prompt != last_prompt or not last_answer:
                        self.log(f"Challenge Type: {data.get('type')}")
                        self.log(f"Question: {data.get('header')} - {data.get('prompt')}")
                        time.sleep(1) # Human-like reading delay
                        
                        answer = self.solve_with_ai(data)
                        if answer:
                            self.log(f"AI Answer: {answer}")
                            last_prompt = current_prompt
                            last_answer = answer
                            consecutive_failures = 0
                        else:
                            last_answer = None
                            consecutive_failures += 1
                    else:
                        # Use cached answer
                        answer = last_answer
                    
                    if not answer:
                        if consecutive_failures > 3:
                            self.log("Multiple failures to get AI answer. Waiting 10s...")
                            time.sleep(10)
                        else:
                            time.sleep(2)
                        continue
                        
                    if data['type'] == "mcq":
                        import json
                        try:
                            parsed_ans = json.loads(answer)
                            clean_ans = parsed_ans.get("answer", answer)
                            if isinstance(clean_ans, list): clean_ans = str(clean_ans)
                            clean_ans = clean_ans.lower().strip()
                        except:
                            clean_ans = answer.lower().strip()
                            
                        clicked = False
                        option_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='challenge-choice'], [role='radio'], button[data-test='challenge-choice']")
                        for opt_elem in option_elements:
                            opt_text = opt_elem.text
                            if '\n' in opt_text: opt_text = opt_text.split('\n', 1)[-1]
                            opt_text = opt_text.lower().strip()
                            
                            if len(opt_text) > 0 and (opt_text == clean_ans or clean_ans in opt_text):
                                self.driver.execute_script("arguments[0].click();", opt_elem)
                                clicked = True
                                self.log(f"Selected option: {opt_text}")
                                time.sleep(0.5)
                                break
                        if not clicked:
                            # Try partial match word by word
                            for opt_elem in option_elements:
                                opt_text = opt_elem.text
                                if '\n' in opt_text: opt_text = opt_text.split('\n', 1)[-1]
                                opt_text = opt_text.lower().strip()
                                
                                # Use regex-like splitting to avoid empty words and check overlap
                                ans_words = [w for w in clean_ans.split() if len(w) > 2]
                                if len(ans_words) > 0 and any(word in opt_text for word in ans_words):
                                    self.driver.execute_script("arguments[0].click();", opt_elem)
                                    clicked = True
                                    self.log(f"Selected option via partial match: {opt_text}")
                                    time.sleep(0.5)
                                    break
                        if not clicked:
                            self.log("Failed to confidently match MCQ option. Retrying next loop.")
                            last_answer = None # Force re-evaluation
                            time.sleep(1)
                            continue
                            
                    elif data['type'] == "wordbank":
                        import json
                        try:
                            parsed_ans = json.loads(answer)
                            answer_tiles = parsed_ans.get("answer", [])
                            if isinstance(answer_tiles, str):
                                answer_tiles = answer_tiles.split()
                        except:
                            answer_tiles = answer.strip().split()
                            
                        clicked_elements = set()
                        for a_tile in answer_tiles:
                            a_tile_clean = str(a_tile).lower().strip()
                            tile_elements = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='word-bank'] button[data-test='challenge-tap-token'], button[data-test='word-bank-tile']")
                            for t_elem in tile_elements:
                                if t_elem not in clicked_elements and t_elem.text.lower().strip() == a_tile_clean and t_elem.is_enabled() and "_1yW_Y" not in t_elem.get_attribute("class"):
                                    self.driver.execute_script("arguments[0].click();", t_elem)
                                    clicked_elements.add(t_elem)
                                    time.sleep(0.15) # Faster delay
                                    break
                                    
                    elif data['type'] == "match":
                        import json
                        try:
                            parsed_ans = json.loads(answer)
                            pairs = parsed_ans.get("answer", [])
                        except:
                            pairs = []
                            for line in answer.strip().split('\n'):
                                tokens = line.split(',')
                                if len(tokens) >= 2:
                                    pairs.append([tokens[0], tokens[1]])
                                    
                        for pair in pairs:
                            if len(pair) >= 2:
                                t1 = str(pair[0]).strip().lower()
                                t2 = str(pair[1]).strip().lower()
                                
                                match_elements = self.driver.find_elements(By.CSS_SELECTOR, "button[data-test='challenge-tap-token']")
                                e1, e2 = None, None
                                for m in match_elements:
                                    m_text = m.text.lower().strip()
                                    if m_text == t1 and not e1 and m.is_enabled() and "_1yW_Y" not in m.get_attribute("class"): e1 = m
                                    elif m_text == t2 and not e2 and m.is_enabled() and "_1yW_Y" not in m.get_attribute("class"): e2 = m
                                
                                if e1 and e2:
                                    self.driver.execute_script("arguments[0].click();", e1)
                                    time.sleep(0.2)
                                    self.driver.execute_script("arguments[0].click();", e2)
                                    time.sleep(0.2)

                    elif data['type'] == "typing":
                        import json
                        try:
                            parsed_ans = json.loads(answer)
                            clean_ans = parsed_ans.get("answer", answer)
                            if isinstance(clean_ans, list): clean_ans = " ".join(clean_ans)
                        except:
                            clean_ans = answer
                            
                        try:
                            input_box = self.driver.find_element(By.CSS_SELECTOR, "textarea[data-test='challenge-translate-input'], input[data-test='challenge-text-input']")
                            input_box.send_keys(Keys.CONTROL + "a")
                            input_box.send_keys(Keys.DELETE)
                            time.sleep(0.1)
                            
                            input_box.send_keys(str(clean_ans).strip())
                            time.sleep(0.2)
                        except Exception as e:
                            self.log(f"Error typing answer: {e}")
                            pass

                    # Click Check
                    time.sleep(1)
                    try:
                        check_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Check')] | //button[@data-test='player-next']")
                        self.driver.execute_script("arguments[0].click();", check_btn)
                        self.log("Clicked Check")
                    except:
                        pass
                
                time.sleep(1) # General loop delay
            except Exception as e:
                self.log(f"Loop error: {e}")
                time.sleep(2)

if __name__ == "__main__":
    print("="*50)
    print(" Duolingo AI Agent (Reliable & Accurate Mode)")
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
        try:
            if any(keyword in agent.driver.current_url for keyword in ["lesson", "practice"]):
                agent.log("Lesson detected! Taking over...")
                agent.run_automation()
            else:
                print("\n" + "="*50)
                user_input = input("Press ENTER to start the next lesson automatically,\nor type 'q' to quit: ")
                if user_input.lower() == 'q':
                    print("Exiting...")
                    agent.driver.quit()
                    break
                    
                agent.log("Starting a new lesson...")
                success = agent.start_lesson()
                if not success:
                    agent.log("Failed to start a lesson automatically. Please click the lesson manually, then the script will take over.")
                
                time.sleep(3)
        except Exception as e:
            if "invalid session id" in str(e).lower() or "disconnected" in str(e).lower():
                print("Browser was closed or disconnected. Exiting script.")
                break
            else:
                agent.log(f"Unexpected error in main loop: {e}")
                time.sleep(3)
