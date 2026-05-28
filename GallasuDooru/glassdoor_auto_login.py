"""
Glassdoor Auto-Login
====================
Handles authentication for glassdoor.co.in using browser cookies and headless Selenium.
"""

import json
import logging
import os
import time
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
AUTH_FILE = os.path.join(BASE_DIR, "glassdoor_auth.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "glassdoor_update.log")
COOKIES_FILE = os.path.join(BASE_DIR, "glassdoor_cookies.json")

# Configure logging
logger = logging.getLogger("glassdoor_login")
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
    logger.info("Attempting background auto-login for Glassdoor...")
    temp_profile = tempfile.mkdtemp(prefix="glassdoor_profile_")
    driver = None
    try:
        options = Options()
        options.add_argument(f"--user-data-dir={temp_profile}")
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        brave_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
        if os.path.exists(brave_path): options.binary_location = brave_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        driver.get("https://www.glassdoor.co.in/profile/login_input.htm")
        time.sleep(5)
        
        if "member" in driver.current_url:
            logger.info("Already logged in.")
        else:
            config = load_config()
            creds = config.get("credentials", {})
            usr = creds.get("username", "")
            pwd = creds.get("password", "")
            
            if usr and pwd:
                logger.info("Injecting Glassdoor credentials...")
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "inlineUserEmail"))).send_keys(usr)
                driver.find_element(By.ID, "inlineUserPassword") # Wait for password field animation
                time.sleep(1)
                driver.find_element(By.ID, "inlineUserPassword").send_keys(pwd)
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                time.sleep(10)
                
                if "member" in driver.current_url or "discovery" in driver.current_url:
                    logger.info("Glassdoor Login successful!")
                else:
                    logger.warning("Glassdoor login might require manual CAPTCHA.")
            else:
                return False

        new_cookies = driver.get_cookies()
        with open(COOKIES_FILE, 'w') as f:
            json.dump(new_cookies, f, indent=4)
        return True

    except Exception as e:
        logger.error(f"Glassdoor Auto-login error: {e}")
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
