"""
Indeed Auto-Apply
==================
Searches for "Indeed Apply" jobs on indeed.com and automates the multi-step dialog.
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
COOKIES_FILE = os.path.join(BASE_DIR, "indeed_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "indeed_update.log")
STATS_FILE = os.path.join(BASE_DIR, "indeed_applied_jobs.json")

logger = logging.getLogger("indeed_apply")
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

def handle_indeed_apply(driver, job_id, jd_text="") -> bool:
    """Handles the multi-step Indeed dialog with AgenticRAG intelligence."""
    wait = WebDriverWait(driver, 10)
    
    # ── AGENTIC RAG SETUP ──
    try:
        from RAG.AgenticRAG.agentic_rag_engine import AgenticRAG
        rag_engine = AgenticRAG()
    except Exception as e:
        logger.error(f"      AgenticRAG load failed: {e}")
        rag_engine = None

    try:
        # Indeed application forms are often in iframes
        time.sleep(2)
        try:
            iframe = driver.find_elements(By.CSS_SELECTOR, "iframe[title='Job application form']")
            if iframe: driver.switch_to.frame(iframe[0])
        except: pass

        for _ in range(12): 
            # 1. AI Solving for text/textarea
            try:
                text_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
                for field in text_fields:
                    if not field.get_attribute("value"):
                        # Attempt to find the label text
                        label = "Job question"
                        try:
                            label_el = driver.find_elements(By.XPATH, f"//label[contains(@for, '{field.get_attribute('id')}')]")
                            if label_el: label = label_el[0].text
                        except: pass
                        logger.info(f"      AgenticRAG Solving: {label}")
                        
                        answer = "I have relevant experience."
                        if rag_engine:
                            rag_answers = rag_engine.plan_and_execute(job_id, f"{jd_text}\nQuestion: {label}")
                            if label in rag_answers:
                                answer = rag_answers[label]
                            elif rag_answers:
                                answer = next(iter(rag_answers.values()))
                        field.send_keys(answer)
            except: pass

            # 2. Click Continue/Next/Submit
            try:
                btn = driver.find_elements(By.XPATH, "//button[contains(span/text(), 'Continue') or contains(text(), 'Continue') or contains(text(), 'Submit') or contains(span/text(), 'Submit')]")
                if btn:
                    driver.execute_script("arguments[0].click();", btn[0])
                    time.sleep(2)
                    continue
            except: pass
            
            # Check if modal closed
            if not driver.find_elements(By.CSS_SELECTOR, "iframe[title='Job application form']"):
                driver.switch_to.default_content()
                return True
        
        driver.switch_to.default_content()
        return True
    except:
        driver.switch_to.default_content()
        return True

def run_auto_apply(dry_run=False):
    config = load_config()
    prefs = config.get("preferences", {})
    keywords = prefs.get("job_titles", [])
    location = prefs.get("location", "Bangalore")
    max_apps = config.get("application", {}).get("max_applications_per_run", 10)
    
    applied_history = [j['job_id'] for j in load_applied_jobs()]
    temp_profile = tempfile.mkdtemp(prefix="indeed_apply_")
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
        
        driver.get("https://in.indeed.com/")
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                for c in cookies:
                    try:
                        driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.indeed.com', 'path': '/'})
                    except: pass
        
        for kw in keywords:
            if applied_count >= max_apps: break
            logger.info(f"Searching Indeed: {kw}")
            url = f"https://in.indeed.com/jobs?q={kw.replace(' ', '+')}&l={location}"
            driver.get(url)
            time.sleep(5)
            
            cards = driver.find_elements(By.CSS_SELECTOR, ".job_seen_beacon")
            for card in cards:
                if applied_count >= max_apps: break
                try:
                    title = card.find_element(By.CSS_SELECTOR, "h2.jobTitle").text.strip()
                    job_id = card.find_element(By.TAG_NAME, "a").get_attribute("data-jk")
                    
                    if job_id in applied_history: continue
                    
                    if dry_run:
                        logger.info(f"  [DRY RUN] Indeed: {title}")
                        applied_count += 1
                        continue

                    driver.execute_script("arguments[0].click();", card)
                    time.sleep(3)
                    
                    # Try to find "Indeed Apply" button
                    try:
                        apply_btn = driver.find_element(By.CSS_SELECTOR, "#indeedApplyButton, .indeed-apply-button")
                        driver.execute_script("arguments[0].click();", apply_btn)
                        if handle_indeed_apply(driver, job_id, ""):
                            save_applied_job(job_id, title, "Indeed Job")
                            applied_count += 1
                            logger.info(f"  ✓ Applied: {title}")
                    except: pass
                        
                except: continue

    except Exception as e:
        logger.error(f"Indeed Auto-Apply Error: {e}")
    finally:
        if driver: driver.quit()
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    run_auto_apply(dry_run='--dry-run' in sys.argv)
