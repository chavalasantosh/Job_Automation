"""
Glassdoor Resume Auto-Uploader (Selenium-Based)
===============================================
Automates Glassdoor resume re-upload.
"""

import os
import json
import logging
import time
import tempfile
import shutil
from typing import Optional

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
COOKIES_FILE = os.path.join(BASE_DIR, "glassdoor_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "glassdoor_update.log")

logger = logging.getLogger("glassdoor_pulse")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def get_resume_path() -> Optional[str]:
    try:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        resume_name = config.get("application", {}).get("resume_path", "SANTOSH CHAVALA.pdf")
        resume_path = os.path.abspath(os.path.join(BASE_DIR, resume_name))
        return resume_path if os.path.exists(resume_path) else None
    except: return None

def upload_glassdoor_resume() -> bool:
    resume_path = get_resume_path()
    if not resume_path: return False
    
    temp_profile = tempfile.mkdtemp(prefix="glassdoor_resume_")
    driver = None
    
    try:
        logger.info(f"[PULSE] Re-uploading Glassdoor resume: {os.path.basename(resume_path)}")
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
        
        driver.get("https://www.glassdoor.co.in/")
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                for c in cookies:
                    try:
                        driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.glassdoor.co.in', 'path': '/'})
                    except: pass
        
        driver.get("https://www.glassdoor.co.in/member/profile/resume.htm")
        time.sleep(5)
        
        file_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        file_input.send_keys(resume_path)
        
        logger.info(f"  ✓ Glassdoor resume uploaded successfully.")
        time.sleep(8)
        return True

    except Exception as e:
        logger.error(f"  ✗ Glassdoor Resume Upload Error: {e}")
        return False
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    upload_glassdoor_resume()
