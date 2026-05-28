"""
Glassdoor Agent - FIXED v3
===========================
Fixes:
  1. act() no longer calls observe() twice — state passed through from run_cycle
  2. Correct Glassdoor India job search URL with proper locId for Bangalore
  3. Widened CSS selectors to match current Glassdoor DOM
  4. Cookie domain fix (glassdoor.co.in vs glassdoor.com)
  5. Debug dump goes to GallasuDooru/ folder
"""

import os
import json
import time
import random
from datetime import datetime
from typing import Dict, Any
from selenium.webdriver.common.by import By
from Agent.SingleAgent.base_agent import BasePortalAgent

ROOT_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_FILE = os.path.join(ROOT_DIR, "GallasuDooru", "config.json")
COOKIES_FILE= os.path.join(ROOT_DIR, "GallasuDooru", "glassdoor_cookies.json")
APPLIED_FILE= os.path.join(ROOT_DIR, "GallasuDooru", "applied_jobs.json")
DEBUG_FILE  = os.path.join(ROOT_DIR, "GallasuDooru", "debug_page.html")

CARD_CSS = (
    "[data-test='jobListing'], "
    "[data-test='job-list-card'], "
    ".jobCard, "
    "[class*='JobCard'], "
    "[class*='job-listing'], "
    "li[class*='JobsList']"
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


class GlassdoorAgent(BasePortalAgent):
    def __init__(self, driver):
        super().__init__(portal_name="Glassdoor", driver=driver)
        self.config      = _load_json(CONFIG_FILE, {})
        self.keywords    = self.config.get("preferences", {}).get("job_titles", ["Generative AI Engineer"])
        self.location    = self.config.get("preferences", {}).get("location", "Bangalore")
        self.max_apps    = self.config.get("application", {}).get("max_applications_per_run", 8)
        self.applied_ids = set(_load_json(APPLIED_FILE, {}).keys())
        self._cookies_injected = False
        self._kw_index   = 0

    def _inject_cookies(self):
        cookies = _load_json(COOKIES_FILE, [])
        if not cookies:
            self.logger.warning("Glassdoor: No cookies found. Check glassdoor_cookies.json.")
            return False
        self.driver.get("https://www.glassdoor.co.in")
        time.sleep(3)
        injected = 0
        for c in cookies:
            try:
                self.driver.add_cookie({
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", ".glassdoor.co.in"),
                    "path":   c.get("path", "/"),
                })
                injected += 1
            except Exception as e:
                self.logger.debug(f"Cookie skip ({c.get('name','')}): {e}")
        self.driver.refresh()
        time.sleep(4)
        self._cookies_injected = True
        self.logger.info(f"Glassdoor: {injected} cookies injected.")
        return True

    def run_cycle(self):
        if self.applied_count >= self.max_apps:
            self.logger.info(f"Glassdoor: Limit reached ({self.max_apps}). Cooling down.")
            self.is_active = False
            return

        if not self._cookies_injected:
            if not self._inject_cookies():
                time.sleep(60)
                return

        keyword = self.keywords[self._kw_index % len(self.keywords)]
        self._kw_index += 1

        # FIXED: Glassdoor India job search URL — locT=C, locName=Bangalore,+Karnataka,+India
        url = (
            f"https://www.glassdoor.co.in/Job/jobs.htm"
            f"?sc.keyword={keyword.replace(' ', '+')}"
            f"&locT=C&locName=Bangalore%2C+Karnataka%2C+India"
            f"&fromAge=7"
        )
        self.logger.info(f"Glassdoor: Searching '{keyword}' in {self.location}...")
        try:
            self.driver.get(url)
            time.sleep(10)
        except Exception as e:
            self.logger.warning(f"Glassdoor: Page load failed: {e}")
            return

        # FIX: Single observe pass
        state = self.observe()
        action = self.think(state)
        self.act(action, state)

    def observe(self) -> Dict[str, Any]:
        state = {"type": "SEARCH_PAGE", "jobs": []}
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_CSS)
            self.logger.info(f"Glassdoor: DOM cards found: {len(cards)}")
            if not cards:
                with open(DEBUG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source[:80000])
                self.logger.warning(f"Glassdoor: 0 cards. Page dumped → {DEBUG_FILE}")

            jobs = []
            for card in cards:
                try:
                    job_id = (card.get_attribute("data-id") or
                              card.get_attribute("data-jobid") or
                              card.get_attribute("id"))
                    title_el = card.find_elements(By.CSS_SELECTOR,
                        "[data-test='job-title'], .job-title, a[class*='jobTitle'], "
                        "[class*='JobCard_jobTitle'], h3, h2")
                    comp_el  = card.find_elements(By.CSS_SELECTOR,
                        "[data-test='employer-name'], .companyName, "
                        "[class*='EmployerProfile_employerName'], [class*='companyName']")
                    if not job_id and title_el:
                        job_id = title_el[0].text.strip()
                    if job_id and job_id not in self.applied_ids:
                        jobs.append({
                            "job_id":  job_id,
                            "title":   title_el[0].text.strip() if title_el else "Glassdoor Job",
                            "company": comp_el[0].text.strip() if comp_el else "Company",
                            "card":    card
                        })
                except Exception:
                    continue
            state["jobs"] = jobs
            self.logger.info(f"Glassdoor: Observed {len(jobs)} new jobs.")
        except Exception as e:
            self.logger.error(f"Glassdoor observe error: {e}")
        return state

    def think(self, state: Dict[str, Any]) -> str:
        return "APPLY_JOBS" if state.get("jobs") else "IDLE"

    # FIX: act() now receives state — no redundant observe()
    def act(self, action: str, state: Dict[str, Any] = None):
        self.logger.info(f"Glassdoor Action: {action}")
        if action == "APPLY_JOBS" and state:
            for job in state.get("jobs", []):
                if self.applied_count >= self.max_apps:
                    break
                self._apply_to_job(job)
                time.sleep(random.uniform(5, 10))

    def _apply_to_job(self, job: Dict):
        try:
            # Click the job card to load the detail panel
            self.driver.execute_script("arguments[0].click();", job["card"])
            time.sleep(3)

            # Look for Easy Apply button in the side panel
            apply_btn = self.driver.find_elements(By.CSS_SELECTOR,
                "button[data-test='applyButton'], "
                "[class*='applyButton'], "
                "button[class*='apply']")
            if not apply_btn:
                self.logger.info(f"Glassdoor: No Easy Apply for '{job['title']}' — skipping.")
                return

            btn_text = apply_btn[0].text
            if "Easy Apply" not in btn_text and "Apply Now" not in btn_text:
                self.logger.info(f"Glassdoor: External apply for '{job['title']}' — skipping.")
                return

            self.driver.execute_script("arguments[0].click();", apply_btn[0])
            time.sleep(3)

            # Walk through modal steps
            for _ in range(8):
                submit = self.driver.find_elements(By.CSS_SELECTOR,
                    "button[data-test='apply-submit'], [class*='submit']")
                if submit:
                    self.driver.execute_script("arguments[0].click();", submit[0])
                    time.sleep(2)
                    break
                nxt = self.driver.find_elements(By.CSS_SELECTOR,
                    "button[data-test='apply-next'], [class*='next']")
                if nxt:
                    self.driver.execute_script("arguments[0].click();", nxt[0])
                    time.sleep(2)
                else:
                    break

            self.applied_ids.add(job["job_id"])
            self.applied_count += 1
            self._save_applied(job)
            self.logger.info(f"Glassdoor: ✓ Applied to '{job['title']}' @ {job['company']}")
        except Exception as e:
            self.logger.error(f"Glassdoor apply error: {e}")

    def _save_applied(self, job: Dict):
        data = _load_json(APPLIED_FILE, {})
        data[job["job_id"]] = {
            "title": job["title"], "company": job["company"],
            "timestamp": datetime.now().isoformat()
        }
        _save_json(APPLIED_FILE, data)
