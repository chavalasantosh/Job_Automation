"""
Foundit Auto-Apply
==================
Searches for jobs on foundit.in and automates "Quick Apply".
Replicates the "Smart Apply" strategy.
"""

import sys
import json
import logging
import random
import tempfile
import shutil
import os
import time
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
NOWCURRY_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'NowCurry'))
if NOWCURRY_DIR not in sys.path:
    sys.path.insert(0, NOWCURRY_DIR)

RAG_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
if RAG_ROOT not in sys.path:
    sys.path.insert(0, RAG_ROOT)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
COOKIES_FILE = os.path.join(BASE_DIR, "foundit_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "foundit_update.log")
STATS_FILE = os.path.join(BASE_DIR, "foundit_applied_jobs.json")

# Configure logging
logger = logging.getLogger("foundit_apply")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = logging.FileHandler(LOG_FILE)
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)
    logger.addHandler(logging.StreamHandler())

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def load_applied_jobs():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except: return []
    return []

def save_applied_job(job_id, title, company):
    applied = load_applied_jobs()
    applied.append({
        "job_id": job_id, "title": title, "company": company,
        "timestamp": datetime.now().isoformat()
    })
    if len(applied) > 1000: applied = applied[-1000:]
    with open(STATS_FILE, 'w') as f:
        json.dump(applied, f, indent=2)

def handle_foundit_dialog(driver, job_id, jd_text="") -> bool:
    """Handles the multi-step Foundit dialog with AgenticRAG."""
    wait = WebDriverWait(driver, 10)
    
    # ── AGENTIC RAG SETUP ──
    try:
        from RAG.AgenticRAG.agentic_rag_engine import AgenticRAG
        rag_engine = AgenticRAG()
    except Exception as e:
        logger.error(f"      AgenticRAG load failed: {e}")
        rag_engine = None

    try:
        for _ in range(10): 
            # 1. Check for Text Questions
            try:
                text_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
                for field in text_fields:
                    if not field.get_attribute("value"):
                        try:
                            label_id = field.get_attribute('id')
                            if label_id:
                                label_elem = driver.find_element(By.XPATH, f"//label[@for='{label_id}']")
                                label = label_elem.text
                            else:
                                label = "What is your relevant experience?"
                            logger.info(f"      AgenticRAG Solving: {label}")
                            
                            answer = "I have relevant experience."
                            if rag_engine:
                                rag_answers = rag_engine.plan_and_execute(job_id, f"{jd_text}\nQuestion: {label}")
                                if label in rag_answers:
                                    answer = rag_answers[label]
                                elif rag_answers:
                                    answer = next(iter(rag_answers.values()))
                            field.send_keys(answer)
                        except Exception as e:
                            logger.debug(f"Field solve error: {e}")
                            field.send_keys("3")
            except: pass

            # 2. Click Apply/Submit/Next
            try:
                btn = driver.find_elements(By.XPATH, "//button[contains(text(), 'Apply') or contains(text(), 'Submit') or contains(text(), 'Next')]")
                if btn:
                    driver.execute_script("arguments[0].click();", btn[0])
                    time.sleep(2)
                    continue
            except: pass
            
            # If nothing found, check if closed
            if not driver.find_elements(By.CSS_SELECTOR, ".modal-content, .application-form"):
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
    
    temp_profile = tempfile.mkdtemp(prefix="foundit_apply_")
    driver = None
    applied_count = 0
    
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
        if os.path.exists(brave_path): options.binary_location = brave_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        
        if stealth_js:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": stealth_js
            })
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
        
        driver.get("https://www.foundit.in/")
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                for c in cookies:
                    try:
                        driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.foundit.in', 'path': '/'})
                    except: pass
        
        for kw in keywords:
            if applied_count >= max_apps: break
            
            logger.info(f"Searching Foundit: {kw}")
            url = f"https://www.foundit.in/srp/results?query={kw.replace(' ', '+')}&locations={location}"
            driver.get(url)
            time.sleep(5)
            
            job_cards = driver.find_elements(By.CSS_SELECTOR, ".card-apply-button, .job-item")
            for card in job_cards:
                if applied_count >= max_apps: break
                try:
                    title = card.find_element(By.CSS_SELECTOR, ".job-title, h3").text.strip()
                    job_id = card.get_attribute("id") or card.get_attribute("data-id")
                    
                    if job_id in applied_history: continue
                    
                    if dry_run:
                        logger.info(f"  [DRY RUN] Foundit: {title}")
                        applied_count += 1
                        continue

                    # Click Quick Apply
                    apply_btn = card.find_element(By.XPATH, ".//button[contains(text(), 'Quick Apply') or contains(text(), 'Apply')]")
                    driver.execute_script("arguments[0].click();", apply_btn)
                    
                    if handle_foundit_dialog(driver, job_id, ""):
                        save_applied_job(job_id, title, "Foundit Job")
                        applied_count += 1
                        logger.info(f"  ✓ Applied: {title}")
                        
                    time.sleep(random.uniform(3, 7))
                except: continue

    except Exception as e:
        logger.error(f"Foundit Auto-Apply Error: {e}")
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    run_auto_apply(dry_run='--dry-run' in sys.argv)
