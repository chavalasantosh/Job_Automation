"""
LinkedIn Auto-Login
===================
LinkedIn requires cookies from a logged-in browser session to bypass complex WAF/CAPTCHA.
This script reads linkedin_cookies.json (exported via EditThisCookie) and builds auth headers.

HOW IT WORKS:
  1. You log into LinkedIn in your browser.
  2. Use "EditThisCookie" extension to export cookies to linkedin_cookies.json.
  3. This script reads them and builds headers for other automation modules.
"""

import sys
import json
import logging
import os
import time
import tempfile
import shutil
from typing import Optional, Dict, Any

# Add NowCurry root for shared Ghost Mode modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOWCURRY_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'NowCurry'))
if NOWCURRY_DIR not in sys.path:
    sys.path.insert(0, NOWCURRY_DIR)
import tempfile
import shutil
from typing import Optional, Dict, Any

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(BASE_DIR, "linkedin_auth.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "linkedin_update.log")
COOKIES_FILE = os.path.join(BASE_DIR, "linkedin_cookies.json")

# Configure logging
logger = logging.getLogger("linkedin_login")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def build_headers_from_cookies() -> Optional[Dict[str, Any]]:
    """Build auth headers from linkedin_cookies.json."""
    if not os.path.exists(COOKIES_FILE):
        logger.error(f"linkedin_cookies.json not found. Export from browser first.")
        return None

    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read cookies file: {e}")
        return None

    cookie_parts = []
    li_at = None
    
    for c in cookies:
        name = c.get('name', '')
        value = c.get('value', '')
        if name and value:
            cookie_parts.append(f"{name}={value}")
            if name == 'li_at':
                li_at = value

    if not li_at:
        logger.warning("linkedin_cookies.json missing 'li_at' cookie. Session might be invalid.")

    headers = {
        "accept": "application/vnd.linkedin.normalized+json+2.1",
        "accept-language": "en-US,en;q=0.9",
        "cookie": "; ".join(cookie_parts),
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "x-li-lang": "en_US",
        "x-restli-protocol-version": "2.0.0"
    }
    
    # CSRF token often required for some LinkedIn APIs (JSESSIONID)
    jsessionid = next((c.get('value') for c in cookies if c.get('name') == 'JSESSIONID'), None)
    if jsessionid:
        headers["csrf-token"] = jsessionid.replace('"', '')

    return headers

def try_auto_login() -> bool:
    """Attempt Zero-Touch auto-login using headless Selenium to refresh cookies."""
    logger.info("Attempting background auto-login via headless browser...")
    temp_profile = tempfile.mkdtemp(prefix="linkedin_profile_")
    driver = None
    try:
        try:
            from stealth_factory import StealthFactory
            stealth_opts = StealthFactory.get_selenium_options()
            stealth_js   = StealthFactory.get_stealth_scripts()
        except ImportError:
            logger.warning("Ghost Mode disabled: StealthFactory not found.")
            stealth_opts, stealth_js = [], ""

        options = Options()
        options.add_argument(f"--user-data-dir={temp_profile}")
        for opt in stealth_opts:
            options.add_argument(opt)
        
        # options.add_argument("--headless=new") # Disabled to prevent net::ERR_CONNECTION_RESET from WAF
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Try to find Brave binary
        brave_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
        if os.path.exists(brave_path):
            options.binary_location = brave_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # Inject Stealth JS before navigation
        if stealth_js:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": stealth_js
            })
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
        
        # 1. Load login page
        driver.get("https://www.linkedin.com/login")
        time.sleep(5)
        
        # 2. Check if already logged in (by looking for feed)
        if "feed" in driver.current_url or "discovery" in driver.current_url:
            logger.info("Already logged in via session reuse.")
        else:
            # 3. Inject credentials
            config = load_config()
            creds = config.get("credentials", {})
            usr = creds.get("username", "")
            pwd = creds.get("password", "")
            
            if usr and pwd:
                logger.info("Injecting credentials...")
                # Based on user capture, common fields are session_key and session_password
                # Selenium often handles this by ID 'username' or 'session_key'
                try:
                    u_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#username, #session_key, input[name='session_key']"))
                    )
                    u_field.clear()
                    u_field.send_keys(usr)
                    
                    p_field = driver.find_element(By.CSS_SELECTOR, "#password, #session_password, input[name='session_password']")
                    p_field.clear()
                    p_field.send_keys(pwd)
                    
                    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .login__form_action_container button")
                    submit_btn.click()
                    
                    logger.info("Credentials submitted! Waiting for server to process login...")
                    time.sleep(10) # Wait for login processing/redirects
                except Exception as inner_e:
                    logger.error(f"Failed to find login fields: {inner_e}")
                    return False
                
                # Check for "Checkpoint" (MFA/CAPTCHA)
                if "checkpoint" in driver.current_url:
                    logger.warning("\n" + "!"*60)
                    logger.warning("!!! LINKEDIN CHECKPOINT DETECTED !!!")
                    logger.warning("LinkedIn is asking for MFA or CAPTCHA.")
                    logger.warning(f"URL: {driver.current_url}")
                    logger.warning("Please log in manually in your browser and re-export cookies.")
                    logger.warning("!"*60 + "\n")
                    return False
                elif "feed" in driver.current_url or "discovery" in driver.current_url:
                    logger.info("Login successful!")
                else:
                    logger.warning(f"Unexpected URL after login: {driver.current_url}")
            else:
                logger.error("No credentials in config.json.")
                return False

        # 4. Extract new cookies
        new_cookies = driver.get_cookies()
        if any(c['name'] == 'li_at' for c in new_cookies):
            # Transform to EditThisCookie format (optional but keeps consistency)
            formatted_cookies = []
            for c in new_cookies:
                formatted_cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c["domain"],
                    "path": c["path"],
                    "secure": c["secure"],
                    "httpOnly": c.get("httpOnly", False)
                })
            
            with open(COOKIES_FILE, 'w') as f:
                json.dump(formatted_cookies, f, indent=4)
            logger.info("Successfully refreshed cookies in the background!")
            return True
        else:
            logger.error("Failed to extract 'li_at' cookie after login attempt.")
            return False

    except Exception as e:
        logger.error(f"Auto-login error: {e}")
        return False
    finally:
        if driver:
            driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

def is_logged_in(driver) -> bool:
    """Verify if the user is logged into LinkedIn by checking the URL and common elements."""
    try:
        # Check for feed or presence of global navigation 'Me' icon
        # We use a shorter timeout here because it's a heartbeat check
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav__me, #global-nav-typeahead, .feed-identity-module"))
        )
        url = driver.current_url
        if "login" in url or "checkpoint" in url:
            logger.warning(f"Session appears to be on a login/checkpoint page: {url}")
            return False
        return True
    except Exception as e:
        logger.debug(f"is_logged_in check failed: {e}")
        return False

def refresh_auth() -> bool:
    """Sync authentication and save to file."""
    # First try building from existing cookies
    headers = build_headers_from_cookies()
    
    # Verify if cookies are actually valid if file exists
    session_valid = False
    if headers and os.path.exists(COOKIES_FILE):
         # If we already have cookies, let's see if they are functional
         # Actually, the most reliable way is try_auto_login which does the page-based check
         pass

    # If no headers or we want to ensure fresh session, try auto-login
    if not headers or not os.path.exists(COOKIES_FILE):
        if try_auto_login():
            headers = build_headers_from_cookies()
    else:
        # Optional: We could do a quick headless check here, 
        # but for performance we might just trust the file and let the main scripts handle retry
        pass

    if headers:
        with open(AUTH_FILE, 'w') as f:
            json.dump(headers, f, indent=4)
        logger.info(f"Auth headers synced to {AUTH_FILE}")
        return True
    return False

if __name__ == "__main__":
    if refresh_auth():
        print("LinkedIn Auth synced successfully!")
    else:
        print("LinkedIn Auth sync failed. Please export cookies manually to linkedin_cookies.json.")
