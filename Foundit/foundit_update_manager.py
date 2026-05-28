"""
Foundit Profile Update Manager (Selenium-Based)
==============================================
Replicates the "Profile Pulse" strategy for foundit.in.
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
COOKIES_FILE = os.path.join(BASE_DIR, "foundit_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "foundit_update.log")

# Configure logging
logger = logging.getLogger("foundit_pulse")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def update_foundit_headline() -> bool:
    """Update Foundit headline using Headless Selenium."""
    config = load_config()
    headlines = config.get("preferences", {}).get("headlines", [])
    if not headlines: return False
    
    headline = random.choice(headlines)
    temp_profile = tempfile.mkdtemp(prefix="foundit_pulse_")
    driver = None
    
    try:
        logger.info(f"[PULSE] Updating Foundit headline to: '{headline}'")
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
        
        driver.get("https://www.foundit.in/")
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                for c in cookies:
                    try:
                        driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.foundit.in', 'path': '/'})
                    except: pass
        
        # Navigate to Profile Page
        driver.get("https://www.foundit.in/mnj/profile")
        time.sleep(5)
        
        # Click Edit Icon for Headline (Structure-based selector)
        edit_icon = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "i.edit-icon, .headline-edit"))
        )
        driver.execute_script("arguments[0].click();", edit_icon)
        time.sleep(2)
        
        textarea = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea#headline, .headline-textarea"))
        )
        textarea.clear()
        textarea.send_keys(headline)
        
        save_btn = driver.find_element(By.CSS_SELECTOR, "button.save-btn, #save-headline")
        driver.execute_script("arguments[0].click();", save_btn)
        time.sleep(3)
        
        logger.info("  ✓ Foundit headline updated successfully.")
        return True

    except Exception as e:
        logger.error(f"  ✗ Foundit Pulse Error: {e}")
        return False
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    update_foundit_headline()
