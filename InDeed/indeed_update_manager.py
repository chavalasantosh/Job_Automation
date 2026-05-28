"""
Indeed Profile Update Manager (Selenium-Based)
==============================================
Handles headline rotation for Indeed profiles.
"""

import os
import json
import logging
import time
import tempfile
import shutil
import random
from typing import List

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
COOKIES_FILE = os.path.join(BASE_DIR, "indeed_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "indeed_update.log")

logger = logging.getLogger("indeed_pulse")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def load_config():
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def update_indeed_headline() -> bool:
    config = load_config()
    headlines = config.get("preferences", {}).get("headlines", [])
    if not headlines: return False
    
    headline = random.choice(headlines)
    temp_profile = tempfile.mkdtemp(prefix="indeed_pulse_")
    driver = None
    
    try:
        logger.info(f"[PULSE] Updating Indeed headline to: '{headline}'")
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
        driver.set_page_load_timeout(45)
        
        driver.get("https://in.indeed.com/")
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                for c in cookies:
                    try:
                        driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.indeed.com', 'path': '/'})
                    except: pass
        
        driver.get("https://profiles.indeed.com/resume")
        time.sleep(5)
        
        # Indeed profile edit
        edit_headline_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Edit headline'], .edit-headline-btn"))
        )
        driver.execute_script("arguments[0].click();", edit_headline_btn)
        time.sleep(2)
        
        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='headline'], #headline-input"))
        )
        input_field.clear()
        input_field.send_keys(headline)
        
        save_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .save-button")
        driver.execute_script("arguments[0].click();", save_btn)
        time.sleep(3)
        
        logger.info("  ✓ Indeed headline updated successfully.")
        return True

    except Exception as e:
        logger.error(f"  ✗ Indeed Pulse Error: {e}")
        return False
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    update_indeed_headline()
