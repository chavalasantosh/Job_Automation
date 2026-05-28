"""
LinkedIn Profile Update Manager (Selenium-Based)
================================================
Automates LinkedIn profile updates (Headline rotation) using Headless Selenium.
Replicates the "Profile Pulse" strategy from NowCurry.
"""

import os
import json
import logging
import time
import tempfile
import shutil
import random
from typing import List, Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
AUTH_FILE = os.path.join(BASE_DIR, "linkedin_auth.json")
COOKIES_FILE = os.path.join(BASE_DIR, "linkedin_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "linkedin_update.log")

# Configure logging
logger = logging.getLogger("linkedin_pulse")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_next_headline(headlines: List[str]) -> str:
    """Select a headline from the pool. Replicated logic from NowCurry."""
    # For now, just pick a random one or use a simple rotation
    # In a full implementation, we might track the last used index in a file
    return random.choice(headlines)

def update_linkedin_headline() -> bool:
    """Update LinkedIn headline using Headless Selenium."""
    config = load_config()
    headlines = config.get("preferences", {}).get("headlines", [])
    if not headlines:
        logger.error("No headlines found in config.json")
        return False
    
    headline = get_next_headline(headlines)
    temp_profile = tempfile.mkdtemp(prefix="linkedin_pulse_")
    driver = None
    
    try:
        logger.info(f"[PULSE] Starting headline update: '{headline}'")
        options = Options()
        options.add_argument(f"--user-data-dir={temp_profile}")
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        brave_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
        if os.path.exists(brave_path):
            options.binary_location = brave_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        
        # 1. Load LinkedIn and inject cookies
        import linkedin_auto_login
        
        def inject_and_verify():
            logger.info("Injecting cookies and verifying session...")
            driver.get("https://www.linkedin.com")
            time.sleep(2)
            if os.path.exists(COOKIES_FILE):
                with open(COOKIES_FILE, 'r') as f:
                    cookies = json.load(f)
                    for c in cookies:
                        try:
                            driver.add_cookie({
                                'name': c['name'],
                                'value': c['value'],
                                'domain': '.linkedin.com',
                                'path': '/'
                            })
                        except: pass
            
            # Navigate to feed to verify
            driver.get("https://www.linkedin.com/feed/")
            time.sleep(5)
            
            if linkedin_auto_login.is_logged_in(driver):
                logger.info("  ✓ Session verified! Logged in as user.")
                return True
            return False

        if not inject_and_verify():
            logger.warning("Session invalid. Attempting background auto-login...")
            if linkedin_auto_login.try_auto_login():
                logger.info("Background login successful, retrying cookie injection...")
                if not inject_and_verify():
                    logger.error("  ✗ Session still invalid after background login.")
                    return False
            else:
                logger.error("  ✗ Background auto-login failed.")
                return False

        # 2. Go to Profile Page
        driver.get("https://www.linkedin.com/in/me/")
        time.sleep(5)
        
        # 3. Click Edit Intro Pencil
        # LinkedIn often has a top card with a pencil icon to edit intro
        logger.info("Opening edit intro modal...")
        edit_intro_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Edit intro')]"))
        )
        driver.execute_script("arguments[0].click();", edit_intro_btn)
        time.sleep(3)
        
        # 4. Find Headline Field and update
        # Inside the modal, the headline is typically an input with name='headline'
        headline_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@label, 'Headline') or @name='headline']"))
        )
        headline_field.clear()
        time.sleep(1)
        headline_field.send_keys(headline)
        time.sleep(1)
        
        # 5. Save
        save_btn = driver.find_element(By.XPATH, "//button[span[text()='Save'] or contains(@aria-label, 'Save')]")
        driver.execute_script("arguments[0].click();", save_btn)
        time.sleep(3)
        
        logger.info(f"  ✓ LinkedIn headline successfully updated to: '{headline}'")
        return True

    except Exception as e:
        logger.error(f"  ✗ Pulse Error: {e}")
        # Save screenshot for debugging if it fails
        try:
            if driver:
                driver.save_screenshot(os.path.join(BASE_DIR, "pulse_error.png"))
                logger.info(f"Screenshot saved to {os.path.join(BASE_DIR, 'pulse_error.png')}")
        except:
            pass
        return False
    finally:
        if driver:
            driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    update_linkedin_headline()
