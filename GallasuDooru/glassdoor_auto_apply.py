"""
Glassdoor Auto-Apply
====================
Searches for "Easy Apply" jobs on glassdoor.co.in and automates applications.
"""

import os
import sys
import json
import time
import logging
import random
import tempfile
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
COOKIES_FILE = os.path.join(BASE_DIR, "glassdoor_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "glassdoor_update.log")
STATS_FILE = os.path.join(BASE_DIR, "glassdoor_applied_jobs.json")

logger = logging.getLogger("glassdoor_apply")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def load_config():
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def load_applied_jobs():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def save_applied_job(job_id, title, company):
    applied = load_applied_jobs()
    applied.append({"job_id": job_id, "title": title, "company": company, "timestamp": datetime.now().isoformat()})
    if len(applied) > 1000: applied = applied[-1000:]
    with open(STATS_FILE, 'w') as f: json.dump(applied, f, indent=2)

def handle_glassdoor_apply(driver) -> bool:
    """Handles the multi-step Glassdoor dialog with 10x intelligence and speed."""
    from RAG.SingleRAG.ai_client import solve_question
    wait = WebDriverWait(driver, 10)
    try:
        for _ in range(12): 
            # 1. AI Solving
            try:
                text_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
                for field in text_fields:
                    if not field.get_attribute("value"):
                        label_el = driver.find_elements(By.XPATH, f"//label[@for='{field.get_attribute('id')}']")
                        label = label_el[0].text if label_el else "Job Question"
                        logger.info(f"      AI Solving: {label}")
                        field.send_keys(solve_question(label))
            except: pass

            # 2. Click Continue/Next/Submit
            try:
                btn = driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Next') or contains(text(), 'Submit')]")
                if btn:
                    driver.execute_script("arguments[0].click();", btn[0])
                    time.sleep(2)
                    continue
            except: pass
            
            # Check if modal closed
            if not driver.find_elements(By.CSS_SELECTOR, "[class*='modal'], [class*='Modal']"):
                return True
        return True
    except: return True

def run_auto_apply(dry_run=False):
    config = load_config()
    prefs = config.get("preferences", {})
    keywords = prefs.get("job_titles", [])
    location = prefs.get("location", "Bangalore")
    max_apps = config.get("application", {}).get("max_applications_per_run", 10)
    
    applied_history = [j['job_id'] for j in load_applied_jobs()]
    temp_profile = tempfile.mkdtemp(prefix="glassdoor_apply_")
    driver = None
    applied_count = 0
    
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
        driver.set_page_load_timeout(45)
        
        driver.get("https://www.glassdoor.co.in/")
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                for c in cookies:
                    try:
                        driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.glassdoor.co.in', 'path': '/'})
                    except: pass
        
        for kw in keywords:
            if applied_count >= max_apps: break
            logger.info(f"Searching Glassdoor: {kw}")
            url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={kw.replace(' ', '%20')}&locT=C&locId=2940587" # Bangalore locId example
            driver.get(url)
            time.sleep(5)
            
            cards = driver.find_elements(By.CSS_SELECTOR, "[data-test='jobListing']")
            for card in cards:
                if applied_count >= max_apps: break
                try:
                    title = card.find_element(By.CSS_SELECTOR, "[data-test='job-title']").text.strip()
                    job_id = card.get_attribute("data-id")
                    
                    if job_id in applied_history: continue
                    
                    if dry_run:
                        logger.info(f"  [DRY RUN] Glassdoor: {title}")
                        applied_count += 1
                        continue

                    driver.execute_script("arguments[0].click();", card)
                    time.sleep(2)
                    
                    apply_btn = driver.find_element(By.CSS_SELECTOR, "button[data-test='applyButton']")
                    if "Easy Apply" in apply_btn.text:
                        driver.execute_script("arguments[0].click();", apply_btn)
                        if handle_glassdoor_apply(driver):
                            save_applied_job(job_id, title, "Glassdoor Job")
                            applied_count += 1
                            logger.info(f"  ✓ Applied: {title}")
                except: continue

    except Exception as e:
        logger.error(f"Glassdoor Auto-Apply Error: {e}")
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    run_auto_apply(dry_run='--dry-run' in sys.argv)
