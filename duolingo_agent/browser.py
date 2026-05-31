"""
Browser engine with anti-detection, persistent sessions, and helper utilities.
Wraps Selenium WebDriver with safe click, wait, and screenshot methods.
"""

import os
import base64
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementNotInteractableException,
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from webdriver_manager.chrome import ChromeDriverManager


class Browser:
    """
    Chrome browser controller with anti-detection and session persistence.

    Features:
        - Removes all automation fingerprints (navigator.webdriver, cdc_ markers)
        - Persistent Chrome profile for session cookies
        - Safe click/type helpers with retry logic
        - Screenshot capture for vision-based AI solving
    """

    def __init__(self, config, logger):
        self.config = config
        self.log = logger
        self.driver = None
        self.wait = None
        self._setup()

    def _setup(self):
        """Initialize Chrome with anti-detection options."""
        options = Options()

        # Headless mode
        if self.config.headless:
            options.add_argument("--headless=new")

        # Custom browser binary
        if self.config.browser_path and os.path.exists(self.config.browser_path):
            options.binary_location = self.config.browser_path
            self.log.info(f"Using custom browser: {self.config.browser_path}")

        # Performance and stability
        options.add_argument("--log-level=3")
        options.add_argument("--mute-audio")
        options.add_argument("--disable-notifications")
        options.add_argument(f"--window-size={self.config.window_width},{self.config.window_height}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")

        # Anti-detection: remove automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Persistent Chrome profile for session reuse
        profile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "chrome_profile"
        )
        options.add_argument(f"user-data-dir={profile_path}")

        # Launch browser
        self.log.info("Launching Chrome...")
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        self.driver.set_page_load_timeout(self.config.page_load_timeout)
        self.wait = WebDriverWait(self.driver, self.config.wait_timeout)

        # Inject anti-detection JavaScript
        self._inject_stealth()
        self.log.success("Browser ready.")

    def _inject_stealth(self):
        """Remove navigator.webdriver and other automation markers via CDP."""
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                        window.chrome = {runtime: {}};
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) =>
                            parameters.name === 'notifications'
                                ? Promise.resolve({state: Notification.permission})
                                : originalQuery(parameters);
                    """
                },
            )
        except Exception:
            self.log.debug("CDP stealth injection skipped (may not affect functionality).")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def get(self, url):
        """Navigate to a URL."""
        self.driver.get(url)

    @property
    def current_url(self):
        """Get the current page URL."""
        return self.driver.current_url

    def url_contains(self, *keywords):
        """Check if the current URL contains any of the given keywords."""
        url = self.current_url.lower()
        return any(kw in url for kw in keywords)

    # ------------------------------------------------------------------
    # Element finders
    # ------------------------------------------------------------------

    def find(self, css_selector):
        """Find a single element by CSS selector. Returns None if not found."""
        try:
            return self.driver.find_element(By.CSS_SELECTOR, css_selector)
        except (NoSuchElementException, StaleElementReferenceException):
            return None

    def find_all(self, css_selector):
        """Find all elements matching a CSS selector."""
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, css_selector)
        except (NoSuchElementException, StaleElementReferenceException):
            return []

    def find_xpath(self, xpath):
        """Find a single element by XPath. Returns None if not found."""
        try:
            return self.driver.find_element(By.XPATH, xpath)
        except (NoSuchElementException, StaleElementReferenceException):
            return None

    def find_all_xpath(self, xpath):
        """Find all elements matching an XPath."""
        try:
            return self.driver.find_elements(By.XPATH, xpath)
        except (NoSuchElementException, StaleElementReferenceException):
            return []

    def wait_for(self, css_selector, timeout=None):
        """Wait for an element to be present in the DOM."""
        t = timeout or self.config.wait_timeout
        try:
            return WebDriverWait(self.driver, t).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
        except TimeoutException:
            return None

    # ------------------------------------------------------------------
    # Safe interactions
    # ------------------------------------------------------------------

    def safe_click(self, element, use_js=True):
        """
        Click an element safely with retry logic.
        Uses JavaScript click by default to bypass overlay issues.
        """
        if element is None:
            return False

        for attempt in range(3):
            try:
                if not element.is_displayed():
                    return False

                if use_js:
                    self.driver.execute_script("arguments[0].click();", element)
                else:
                    element.click()
                return True

            except StaleElementReferenceException:
                self.log.debug(f"Stale element on click attempt {attempt + 1}")
                time.sleep(0.2)
            except ElementNotInteractableException:
                self.log.debug(f"Element not interactable on attempt {attempt + 1}")
                # Try scrolling into view
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", element
                    )
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception:
                    time.sleep(0.2)
            except Exception:
                time.sleep(0.2)

        return False

    def safe_type(self, element, text):
        """Clear an input element and type text into it."""
        if element is None:
            return False
        try:
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
            time.sleep(0.1)
            element.send_keys(str(text))
            return True
        except Exception as e:
            self.log.error(f"Failed to type text: {e}")
            return False

    # ------------------------------------------------------------------
    # Screenshot for vision API
    # ------------------------------------------------------------------

    def take_screenshot_base64(self):
        """Capture the current page as a base64-encoded PNG string."""
        try:
            return self.driver.get_screenshot_as_base64()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Click buttons by text content
    # ------------------------------------------------------------------

    def click_button_by_text(self, *texts, partial=True):
        """
        Find and click a visible button whose text matches any of the given strings.
        Returns True if a button was clicked, False otherwise.
        """
        buttons = self.find_all("button")
        for btn in buttons:
            try:
                if not btn.is_displayed() or not btn.is_enabled():
                    continue
                btn_text = btn.text.strip().lower()
                for target in texts:
                    target_lower = target.lower()
                    if partial and target_lower in btn_text:
                        return self.safe_click(btn)
                    elif not partial and btn_text == target_lower:
                        return self.safe_click(btn)
            except StaleElementReferenceException:
                continue
        return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def quit(self):
        """Close the browser."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

    @property
    def is_alive(self):
        """Check if the browser session is still valid."""
        try:
            _ = self.driver.current_url
            return True
        except (WebDriverException, Exception):
            return False
