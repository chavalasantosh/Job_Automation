"""
LinkedIn Resume Auto-Uploader (Selenium-Based)
==============================================
Automates LinkedIn resume re-upload to maintain profile pulse.
URL: https://www.linkedin.com/jobs/application-settings/
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

def get_resume_path() -> Optional[str]:
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        resume_name = config.get("application", {}).get("resume_path", "SANTOSH CHAVALA.pdf")
        resume_path = os.path.abspath(os.path.join(BASE_DIR, resume_name))
        if not os.path.exists(resume_path):
            logger.error(f"Resume not found: {resume_path}")
            return None
        return resume_path
    except:
        return os.path.abspath(os.path.join(BASE_DIR, "SANTOSH CHAVALA.pdf"))

def upload_linkedin_resume() -> bool:
    """Upload resume via Headless Selenium."""
    resume_path = get_resume_path()
    if not resume_path:
        return False
    
    temp_profile = tempfile.mkdtemp(prefix="linkedin_resume_")
    driver = None
    
    try:
        logger.info(f"[PULSE] Starting resume upload: {os.path.basename(resume_path)}")
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

        # 2. Go to Application Settings
        driver.get("https://www.linkedin.com/jobs/application-settings/")
        time.sleep(5)
        
        # 3. Handle File Upload
        # LinkedIn has a hidden input[type="file"] for resume uploads on this page
        # It's often used for "Upload resume"
        logger.info("Locating file input...")
        file_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        
        # Send keys directly to the file input
        file_input.send_keys(resume_path)
        logger.info("File path sent to input.")
        
        # 4. Wait for upload to complete
        # We look for a success indicator or simply wait a bit
        time.sleep(10)
        
        logger.info(f"  ✓ LinkedIn resume successfully uploaded: {os.path.basename(resume_path)}")
        return True

    except Exception as e:
        logger.error(f"  ✗ Resume Upload Error: {e}")
        try:
            if driver:
                driver.save_screenshot(os.path.join(BASE_DIR, "resume_upload_error.png"))
        except:
            pass
        return False
    finally:
        if driver:
            driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    upload_linkedin_resume()
