import sys
import json
import logging
import random
import tempfile
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

# Ensure RAG module is reachable
RAG_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
if RAG_ROOT not in sys.path:
    sys.path.insert(0, RAG_ROOT)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
COOKIES_FILE = os.path.join(BASE_DIR, "linkedin_cookies.json")
LOG_FILE = os.path.join(BASE_DIR, "linkedin_update.log")
STATS_FILE = os.path.join(BASE_DIR, "linkedin_applied_jobs.json")

# Configure logging
logger = logging.getLogger("linkedin_apply")
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
        except:
            return []
    return []

def save_applied_job(job_id, title, company):
    applied = load_applied_jobs()
    applied.append({
        "job_id": job_id,
        "title": title,
        "company": company,
        "timestamp": datetime.now().isoformat()
    })
    # Keep last 1000
    if len(applied) > 1000:
        applied = applied[-1000:]
    with open(STATS_FILE, 'w') as f:
        json.dump(applied, f, indent=2)

from selenium.webdriver.support.ui import WebDriverWait

def handle_apply_dialog(driver, job_id, jd_text="") -> bool:
    """Handles the multi-step Easy Apply dialog with AgenticRAG intelligence."""
    wait = WebDriverWait(driver, 10)
    
    # ── AGENTIC RAG SETUP ──
    try:
        from RAG.AgenticRAG.agentic_rag_engine import AgenticRAG
        rag_engine = AgenticRAG()
    except Exception as e:
        logger.error(f"      AgenticRAG load failed: {e}")
        rag_engine = None

    try:
        for _ in range(15): # Max 15 steps for complex forms
            # 1. Check for Submit button
            try:
                submit_btn = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Submit application') or span[text()='Submit application']]")
                if submit_btn:
                    driver.execute_script("arguments[0].click();", submit_btn[0])
                    logger.info("      ✓ Clicked Submit!")
                    return True
            except: pass

            # 2. Check for Text Questions (AI Integration)
            try:
                text_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
                for field in text_fields:
                    if not field.get_attribute("value"): # If empty
                        try:
                            label_id = field.get_attribute('id')
                            if label_id:
                                label_elem = driver.find_element(By.XPATH, f"//label[@for='{label_id}']")
                                label = label_elem.text
                            else:
                                label = "What is your relevant experience?" # fallback
                            logger.info(f"      AgenticRAG Solving: {label}")
                            
                            answer = "I have extensive experience."
                            if rag_engine:
                                # We treat the label as the question
                                rag_answers = rag_engine.plan_and_execute(job_id, f"{jd_text}\nQuestion: {label}")
                                if label in rag_answers:
                                    answer = rag_answers[label]
                                elif rag_answers:
                                    answer = next(iter(rag_answers.values()))
                                    
                            field.send_keys(answer)
                        except Exception as e:
                            logger.debug(f"Field solve error: {e}")
                            field.send_keys("3") # safe naive fallback
            except: pass

            # 3. Check for Next/Review/Continue
            try:
                next_btn = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Continue to next step') or span[text()='Next'] or span[text()='Review']]")
                if next_btn:
                    driver.execute_script("arguments[0].click();", next_btn[0])
                    logger.info("      -> Moving to next step...")
                    time.sleep(1) # Small wait for animation
                    continue
            except: pass

            # 4. If nothing found, check if dialog is closed
            if not driver.find_elements(By.CSS_SELECTOR, ".jobs-easy-apply-modal"):
                return True
            
            time.sleep(1) # Backup delay
        
        return False
    except Exception as e:
        logger.error(f"      ✗ Apply Dialog Error: {e}")
        return False

def run_auto_apply(dry_run=False, continuous_mode=False):
    config = load_config()
    prefs = config.get("preferences", {})
    keywords = prefs.get("job_titles", [])
    location = prefs.get("location", "Bangalore")
    max_apps = config.get("application", {}).get("max_applications_per_run", 10)
    
    applied_history = [j['job_id'] for j in load_applied_jobs()]
    
    temp_profile = tempfile.mkdtemp(prefix="linkedin_apply_")
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
            
        # options.add_argument("--headless=new") # Disabled to prevent net::ERR_CONNECTION_RESET
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        brave_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "BraveSoftware", "Brave-Browser", "Application", "brave.exe")
        if os.path.exists(brave_path):
            options.binary_location = brave_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        
        if stealth_js:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": stealth_js
            })
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
        
        # 1. Login/Inject Cookies
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
                            # Use domain .linkedin.com for sharing across subdomains
                            driver.add_cookie({'name': c['name'], 'value': c['value'], 'domain': '.linkedin.com', 'path': '/'})
                        except: pass
            
            # Navigate to feed to verify
            driver.get("https://www.linkedin.com/feed/")
            time.sleep(5)
            
            if linkedin_auto_login.is_logged_in(driver):
                logger.info("  [SUCCESS] Session verified! Logged in as user.")
                return True
            return False

        if not inject_and_verify():
            logger.warning("Session invalid after cookie injection. Attempting background auto-login...")
            if linkedin_auto_login.try_auto_login():
                logger.info("Background login successful, retrying cookie injection...")
                if not inject_and_verify():
                    logger.error("  [FAILED] Session still invalid after background login. Manual login required.")
                    return
            else:
                logger.error("  [FAILED] Background auto-login failed. Please run login_helper.py manually.")
                return

        # 2. Start Search Loop
        for kw in keywords:
            if applied_count >= max_apps: break
            
            logger.info(f"Searching for: {kw} in {location}")
            time_filter = "&f_TPR=r86400" if continuous_mode else ""
            search_url = f"https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords={kw.replace(' ', '%20')}&location={location.replace(' ', '%20')}{time_filter}"
            driver.get(search_url)
            time.sleep(5)
            
            # 2. Iterate through Job Cards
            try:
                job_cards = driver.find_elements(By.CSS_SELECTOR, ".job-card-container")
                logger.info(f"  Found {len(job_cards)} jobs on this page.")
                
                for card in job_cards:
                    if applied_count >= max_apps: break
                    
                    try:
                        # Extract Job Info
                        title = card.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__title").text.strip()
                        company = card.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle").text.strip()
                        job_id = card.get_attribute("data-job-id")
                        
                        if job_id in applied_history:
                            logger.info(f"  Skipping already applied: {title} @ {company}")
                            continue

                        logger.info(f"  Processing: {title} @ {company} (ID: {job_id})")
                        
                        if dry_run:
                            logger.info("    [DRY RUN] Would apply here.")
                            applied_count += 1
                            continue

                        # Click Job Card
                        driver.execute_script("arguments[0].click();", card)
                        time.sleep(3)
                        
                        # Click Easy Apply
                        try:
                            apply_btn = driver.find_element(By.CSS_SELECTOR, "button.jobs-apply-button")
                            if "Easy Apply" in apply_btn.text:
                                driver.execute_script("arguments[0].click();", apply_btn)
                                time.sleep(2)
                                
                                if handle_apply_dialog(driver, job_id, ""):
                                    save_applied_job(job_id, title, company)
                                    applied_count += 1
                                    logger.info(f"    [SUCCESS] Applied successfully!")
                                else:
                                    logger.warning(f"    [FAILED] Failed to finish apply dialog.")
                            else:
                                logger.info("    Standard Apply (not Easy Apply), skipping.")
                        except NoSuchElementException:
                            logger.info("    No Apply button found or already applied.")
                        
                        time.sleep(random.uniform(5, 10)) # Human-like delay
                        
                    except Exception as e:
                        logger.error(f"  Error processing job card: {e}")
                        
            except Exception as e:
                logger.error(f"Error finding job cards: {e}")

        logger.info(f"Auto-apply run finished. Applied to {applied_count} jobs.")

    except Exception as e:
        logger.error(f"Global Auto-Apply Error: {e}")
    finally:
        if driver: driver.quit()
        import shutil
        shutil.rmtree(temp_profile, ignore_errors=True)

if __name__ == "__main__":
    run_auto_apply(dry_run='--dry-run' in sys.argv)
