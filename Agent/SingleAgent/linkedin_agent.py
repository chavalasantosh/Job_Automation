"""
LinkedIn Agent - FIXED v3
==========================
Fixes:
  1. act() no longer calls observe() twice — state passed through
  2. Correct Easy Apply filter URL param (f_LF=f_AL)
  3. Widened job card selectors
  4. Cookie file warning is clear and actionable
"""

import os
import json
import time
import random
from datetime import datetime
from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from Agent.SingleAgent.base_agent import BasePortalAgent

ROOT_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_FILE = os.path.join(ROOT_DIR, "LinkieDin", "config.json")
COOKIES_FILE= os.path.join(ROOT_DIR, "LinkieDin", "linkedin_cookies.json")
APPLIED_FILE= os.path.join(ROOT_DIR, "LinkieDin", "linkedin_applied_jobs.json")
DEBUG_FILE  = os.path.join(ROOT_DIR, "LinkieDin", "debug_page.html")

CARD_CSS = (
    ".job-card-container, "
    "[class*='job-card-container'], "
    ".jobs-search-results__list-item, "
    "[data-occludable-job-id]"
)


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class LinkedInAgent(BasePortalAgent):
    def __init__(self, driver):
        super().__init__(portal_name="LinkedIn", driver=driver)
        self.config      = _load_json(CONFIG_FILE, {})
        self.keywords    = self.config.get("preferences", {}).get("job_titles", ["Generative AI Engineer"])
        self.location    = self.config.get("preferences", {}).get("location", "Bangalore")
        self.max_apps    = self.config.get("application", {}).get("max_applications_per_run", 25)
        self.applied_ids = set(j["job_id"] for j in _load_json(APPLIED_FILE, []))
        self._cookies_injected = False
        self._kw_index   = 0

    def _inject_cookies(self):
        cookies = _load_json(COOKIES_FILE, [])
        if not cookies:
            self.logger.warning("LinkedIn: No cookies found. Attempting auto-login...")
            return self._auto_login()

        self.driver.get("https://www.linkedin.com")
        time.sleep(3)
        injected = 0
        for c in cookies:
            try:
                self.driver.add_cookie({
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", ".linkedin.com"),
                    "path":   c.get("path", "/"),
                })
                injected += 1
            except Exception as e:
                self.logger.debug(f"Cookie skip ({c.get('name','')}): {e}")
        self.driver.refresh()
        time.sleep(5)
        
        # Verify if cookies worked (if we are on login page, they failed)
        if "login" in self.driver.current_url or "session_key" in self.driver.page_source:
            self.logger.warning("LinkedIn: Cookies expired or invalid. Attempting auto-login...")
            return self._auto_login()

        self._cookies_injected = True
        self.logger.info(f"LinkedIn: {injected} cookies injected and session valid.")
        return True

    def _auto_login(self):
        creds = self.config.get("credentials", {})
        usr = creds.get("username", "")
        pwd = creds.get("password", "")
        if not usr or not pwd:
            self.logger.error("LinkedIn: No credentials in config.json to auto-login. Cannot proceed.")
            return False

        self.logger.info("LinkedIn: Starting auto-login sequence...")
        self.driver.get("https://www.linkedin.com/login")
        time.sleep(5)

        try:
            u_field = self.driver.find_element(By.CSS_SELECTOR, "#username, #session_key, input[name='session_key']")
            u_field.clear()
            u_field.send_keys(usr)
            
            p_field = self.driver.find_element(By.CSS_SELECTOR, "#password, #session_password, input[name='session_password']")
            p_field.clear()
            p_field.send_keys(pwd)
            
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.driver.execute_script("arguments[0].click();", submit_btn)
            
            self.logger.info("LinkedIn: Credentials submitted. Waiting for login to process...")
            time.sleep(10)
            
            # Check for CAPTCHA/Checkpoint
            if "checkpoint" in self.driver.current_url or "challenge" in self.driver.current_url:
                self.logger.error("LinkedIn: CHECKPOINT DETECTED (MFA/CAPTCHA). Cannot auto-login.")
                return False

            if "feed" in self.driver.current_url or "discovery" in self.driver.current_url or "jobs" in self.driver.current_url:
                self.logger.info("LinkedIn: Login successful. Extracting fresh cookies...")
                new_cookies = self.driver.get_cookies()
                if any(c['name'] == 'li_at' for c in new_cookies):
                    _save_json(COOKIES_FILE, new_cookies)
                    self._cookies_injected = True
                    return True
                else:
                    self.logger.error("LinkedIn: Login seemed successful but 'li_at' cookie is missing.")
                    return False
            else:
                self.logger.error(f"LinkedIn: Unknown URL after login: {self.driver.current_url}")
                return False
        except Exception as e:
            self.logger.error(f"LinkedIn: Auto-login failed: {e}")
            return False

    def run_cycle(self):
        if self.applied_count >= self.max_apps:
            self.logger.info(f"LinkedIn: Limit reached ({self.max_apps}). Cooling down.")
            self.is_active = False
            return

        if not self._cookies_injected:
            if not self._inject_cookies():
                time.sleep(120)  # wait longer before retrying missing cookies
                return

        keyword = self.keywords[self._kw_index % len(self.keywords)]
        self._kw_index += 1
        # f_LF=f_AL = Easy Apply filter
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?f_LF=f_AL"
            f"&keywords={keyword.replace(' ', '%20')}"
            f"&location={self.location.replace(' ', '%20')}"
            f"&f_TPR=r86400"  # last 24 hours
        )
        self.logger.info(f"LinkedIn: Searching '{keyword}' in {self.location}...")
        try:
            self.driver.get(url)
            time.sleep(10)
        except Exception as e:
            self.logger.warning(f"LinkedIn: Page load failed: {e}")
            return

        # FIX: Single observe pass
        state = self.observe()
        action = self.think(state)
        self.act(action, state)

    def observe(self) -> Dict[str, Any]:
        state = {"type": "SEARCH_PAGE", "jobs": []}
        try:
            # Check for open apply modal first
            if self.driver.find_elements(By.CSS_SELECTOR, ".jobs-easy-apply-modal"):
                state["type"] = "APPLY_DIALOG"
                return state

            cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_CSS)
            self.logger.info(f"LinkedIn: DOM cards found: {len(cards)}")
            if not cards:
                with open(DEBUG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source[:80000])
                self.logger.warning(f"LinkedIn: 0 cards. Page dumped → {DEBUG_FILE}")

            jobs = []
            for card in cards:
                try:
                    job_id = (card.get_attribute("data-job-id") or
                              card.get_attribute("data-occludable-job-id") or
                              card.get_attribute("data-entity-urn"))
                    title_el = card.find_elements(By.CSS_SELECTOR,
                        ".artdeco-entity-lockup__title, "
                        "[class*='job-card-list__title'], "
                        "a[class*='job-card']")
                    comp_el  = card.find_elements(By.CSS_SELECTOR,
                        ".artdeco-entity-lockup__subtitle, "
                        "[class*='job-card-container__company-name']")
                    if not job_id and title_el:
                        job_id = title_el[0].text.strip()
                    if job_id and job_id not in self.applied_ids:
                        jobs.append({
                            "job_id":  job_id,
                            "title":   title_el[0].text.strip() if title_el else "LinkedIn Job",
                            "company": comp_el[0].text.strip() if comp_el else "Company",
                            "card":    card
                        })
                except Exception:
                    continue
            state["jobs"] = jobs
            self.logger.info(f"LinkedIn: Observed {len(jobs)} new jobs.")
        except Exception as e:
            self.logger.error(f"LinkedIn observe error: {e}")
        return state

    def think(self, state: Dict[str, Any]) -> str:
        if state["type"] == "APPLY_DIALOG":
            return "HANDLE_DIALOG"
        if state.get("jobs"):
            return "APPLY_JOBS"
        return "IDLE"

    # FIX: act() receives state — no redundant second observe()
    def act(self, action: str, state: Dict[str, Any] = None):
        self.logger.info(f"LinkedIn Action: {action}")
        if action == "APPLY_JOBS" and state:
            for job in state.get("jobs", []):
                if self.applied_count >= self.max_apps:
                    break
                self._apply_to_job(job)
                time.sleep(random.uniform(6, 12))
        elif action == "HANDLE_DIALOG":
            self._handle_easy_apply_dialog()

    def _apply_to_job(self, job: Dict):
        try:
            self.driver.execute_script("arguments[0].click();", job["card"])
            time.sleep(3)
            apply_btn = self.driver.find_elements(By.CSS_SELECTOR,
                "button.jobs-apply-button, [class*='jobs-apply-button']")
            if not apply_btn:
                return
            btn_text = apply_btn[0].text
            if "Easy Apply" not in btn_text:
                self.logger.info(f"LinkedIn: No Easy Apply for '{job['title']}' — skipping.")
                return
            self.driver.execute_script("arguments[0].click();", apply_btn[0])
            time.sleep(2)
            success = self._handle_easy_apply_dialog()
            if success:
                self.applied_ids.add(job["job_id"])
                self.applied_count += 1
                self._save_applied(job)
                self.logger.info(f"LinkedIn: ✓ Applied to '{job['title']}' @ {job['company']}")
            else:
                self.logger.warning(f"LinkedIn: ✗ Dialog incomplete for '{job['title']}'")
        except Exception as e:
            self.logger.error(f"LinkedIn apply error: {e}")

    def _handle_easy_apply_dialog(self) -> bool:
        for _ in range(15):
            time.sleep(1.5)
            try:
                fields = self.driver.find_elements(By.CSS_SELECTOR,
                    "input[type='text']:not([value]), textarea")
                for field in fields:
                    if not field.get_attribute("value"):
                        label_el = self.driver.find_elements(By.XPATH,
                            f"//label[@for='{field.get_attribute('id')}']")
                        label = label_el[0].text if label_el else "Experience question"
                        answer = self.solve_screening_question(label)
                        field.send_keys(answer)
            except Exception:
                pass
            # Submit
            submit = self.driver.find_elements(By.XPATH,
                "//button[contains(@aria-label,'Submit application')]")
            if submit:
                self.driver.execute_script("arguments[0].click();", submit[0])
                time.sleep(2)
                return True
            # Next / Review / Continue
            nxt = self.driver.find_elements(By.XPATH,
                "//button[contains(@aria-label,'Continue') or .//span[text()='Next'] or .//span[text()='Review']]")
            if nxt:
                self.driver.execute_script("arguments[0].click();", nxt[0])
                continue
            if not self.driver.find_elements(By.CSS_SELECTOR, ".jobs-easy-apply-modal"):
                return True
        return False

    def _save_applied(self, job: Dict):
        data = _load_json(APPLIED_FILE, [])
        data.append({
            "job_id": job["job_id"], "title": job["title"],
            "company": job["company"], "timestamp": datetime.now().isoformat()
        })
        _save_json(APPLIED_FILE, data[-1000:])
