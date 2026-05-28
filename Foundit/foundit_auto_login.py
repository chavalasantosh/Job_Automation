"""
Foundit Auto-Login
==================
Handles authentication for foundit.in using browser cookies and headless Selenium.
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

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(BASE_DIR, "foundit_auth.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "foundit_update.log")
COOKIES_FILE = os.path.join(BASE_DIR, "foundit_cookies.json")

# Configure logging
logger = logging.getLogger("foundit_login")
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
    if not os.path.exists(COOKIES_FILE):
        return None

    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read cookies file: {e}")
        return None

    cookie_parts = []
    for c in cookies:
        name = c.get('name', '')
        value = c.get('value', '')
        if name and value:
            cookie_parts.append(f"{name}={value}")

    headers = {
        "cookie": "; ".join(cookie_parts),
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    return headers

def try_auto_login() -> bool:
    logger.info("Attempting background auto-login via headless browser for Foundit...")
    temp_profile = tempfile.mkdtemp(prefix="foundit_profile_")
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
        
        # options.add_argument("--headless=new")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        brave_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
        if os.path.exists(brave_path):
            options.binary_location = brave_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        if stealth_js:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": stealth_js
            })
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
        
        driver.get("https://www.foundit.in/login")
        time.sleep(5)
        
        if "dashboard" in driver.current_url:
            logger.info("Already logged in via session reuse.")
        else:
            config = load_config()
            creds = config.get("credentials", {})
            usr = creds.get("username", "")
            pwd = creds.get("password", "")
            
            if usr and pwd:
                logger.info("Injecting credentials...")
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "signInName"))).send_keys(usr)
                driver.find_element(By.ID, "password").send_keys(pwd)
                driver.find_element(By.ID, "login-submit").click()
                time.sleep(10)
                
                if "dashboard" in driver.current_url:
                    logger.info("Foundit Login successful!")
                else:
                    logger.warning("Foundit login trigger checkpoint or failed.")
            else:
                return False

        new_cookies = driver.get_cookies()
        with open(COOKIES_FILE, 'w') as f:
            json.dump(new_cookies, f, indent=4)
        return True

    except Exception as e:
        logger.error(f"Foundit Auto-login error: {e}")
        return False
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

def refresh_auth() -> bool:
    headers = build_headers_from_cookies()
    if not headers:
        if try_auto_login():
            headers = build_headers_from_cookies()

    if headers:
        with open(AUTH_FILE, 'w') as f:
            json.dump(headers, f, indent=4)
        return True
    return False

if __name__ == "__main__":
    refresh_auth()
