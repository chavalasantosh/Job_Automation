"""
Foundit Agent - FIXED v3
========================
Fixes:
  1. act() no longer calls observe() a second time (wasted the jobs list)
  2. Cookie injection uses exact domain from cookie file
  3. Correct Foundit SRP URL format
  4. Widest possible CSS selector net for job cards
  5. Debug HTML dump goes to Foundit/ folder (findable)
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
CONFIG_FILE = os.path.join(ROOT_DIR, "Foundit", "config.json")
COOKIES_FILE= os.path.join(ROOT_DIR, "Foundit", "foundit_cookies.json")
APPLIED_FILE= os.path.join(ROOT_DIR, "Foundit", "applied_jobs.json")
DEBUG_FILE  = os.path.join(ROOT_DIR, "Foundit", "debug_page.html")

# Union of all known Foundit card selectors
CARD_CSS = (
    ".srpResultCard, .job-apply-card, .job-item, "
    "[class*='jobTuple'], [class*='job-card'], article[data-id], "
    "[class*='cardContainer'], [class*='tupleWrapper']"
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


class FounditAgent(BasePortalAgent):
    def __init__(self, driver):
        super().__init__(portal_name="Foundit", driver=driver)
        self.config      = _load_json(CONFIG_FILE, {})
        self.keywords    = self.config.get("preferences", {}).get("job_titles", ["Generative AI Engineer"])
        self.location    = self.config.get("preferences", {}).get("location", "Bangalore")
        self.max_apps    = self.config.get("application", {}).get("max_applications_per_run", 10)
        self.applied_ids = set(_load_json(APPLIED_FILE, {}).keys())
        self._cookies_injected = False
        self._kw_index   = 0

    def _inject_cookies(self):
        cookies = _load_json(COOKIES_FILE, [])
        if not cookies:
            self.logger.warning("Foundit: No cookies found. Check foundit_cookies.json.")
            return False
        self.driver.get("https://www.foundit.in")
        time.sleep(3)
        injected = 0
        for c in cookies:
            try:
                self.driver.add_cookie({
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", ".foundit.in"),
                    "path":   c.get("path", "/"),
                })
                injected += 1
            except Exception as e:
                self.logger.debug(f"Cookie skip ({c.get('name','')}): {e}")
        self.driver.refresh()
        time.sleep(4)
        self._cookies_injected = True
        self.logger.info(f"Foundit: {injected} cookies injected.")
        return True

    def run_cycle(self):
        if self.applied_count >= self.max_apps:
            self.logger.info(f"Foundit: Limit reached ({self.max_apps}). Cooling down.")
            self.is_active = False
            return

        if not self._cookies_injected:
            if not self._inject_cookies():
                time.sleep(60)
                return

        keyword = self.keywords[self._kw_index % len(self.keywords)]
        self._kw_index += 1
        url = (
            f"https://www.foundit.in/srp/results"
            f"?query={keyword.replace(' ', '+')}"
            f"&locations={self.location.replace(' ', '+')}"
        )
        self.logger.info(f"Foundit: Searching '{keyword}' in {self.location}...")
        try:
            self.driver.get(url)
            time.sleep(10)
        except Exception as e:
            self.logger.warning(f"Foundit: Page load failed: {e}")
            return

        # FIX: observe once, pass result through — never call observe() again
        state = self.observe()
        action = self.think(state)
        self.act(action, state)

    def observe(self) -> Dict[str, Any]:
        state = {"type": "SEARCH_PAGE", "jobs": []}
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_CSS)
            self.logger.info(f"Foundit: DOM cards found: {len(cards)}")
            if not cards:
                with open(DEBUG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source[:80000])
                self.logger.warning(f"Foundit: 0 cards. Page dumped → {DEBUG_FILE}")

            jobs = []
            for card in cards:
                try:
                    job_id = (card.get_attribute("data-id") or
                              card.get_attribute("data-job-id") or
                              card.get_attribute("id"))
                    title_el = card.find_elements(By.CSS_SELECTOR,
                        "a[title], .jobTitle, h3 a, .title, [class*='jobTitle']")
                    comp_el  = card.find_elements(By.CSS_SELECTOR,
                        ".companyName, .company-name, [class*='company']")
                    if not job_id and title_el:
                        job_id = title_el[0].text.strip()  # fallback dedup key
                    if job_id and job_id not in self.applied_ids:
                        jobs.append({
                            "job_id":  job_id,
                            "title":   (title_el[0].get_attribute("title") or title_el[0].text.strip()) if title_el else "Foundit Job",
                            "company": comp_el[0].text.strip() if comp_el else "Company",
                            "card":    card
                        })
                except Exception:
                    continue
            state["jobs"] = jobs
            self.logger.info(f"Foundit: Observed {len(jobs)} new jobs.")
        except Exception as e:
            self.logger.error(f"Foundit observe error: {e}")
        return state

    def think(self, state: Dict[str, Any]) -> str:
        return "APPLY_JOBS" if state.get("jobs") else "IDLE"

    # FIX: act() receives state — but re-fetches card by index to avoid StaleElement
    def act(self, action: str, state: Dict[str, Any] = None):
        self.logger.info(f"Foundit Action: {action}")
        if action == "APPLY_JOBS" and state:
            jobs = state.get("jobs", [])
            for i, job in enumerate(jobs):
                if self.applied_count >= self.max_apps:
                    break
                # Re-fetch all cards fresh to avoid StaleElementReferenceException
                try:
                    live_cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_CSS)
                    if i < len(live_cards):
                        job["card"] = live_cards[i]
                except Exception:
                    pass
                self._apply_to_job(job)
                time.sleep(random.uniform(5, 10))

    def _apply_to_job(self, job: Dict):
        try:
            # Try quick-apply button directly on card first
            quick = job["card"].find_elements(By.CSS_SELECTOR,
                "button[class*='apply'], button[class*='Apply'], .applyButton, [class*='quickApply']")
            if quick:
                self.driver.execute_script("arguments[0].click();", quick[0])
                time.sleep(3)
            else:
                # Open job detail
                link = job["card"].find_elements(By.CSS_SELECTOR,
                    "a[href*='/job/'], a.title, a.jobTitle, h3 a")
                if not link:
                    return
                self.driver.execute_script("arguments[0].click();", link[0])
                time.sleep(4)
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                btn = self.driver.find_elements(By.CSS_SELECTOR,
                    "#applyJobContainer button, .action-apply, button[class*='apply']")
                if not btn:
                    self.logger.info("Foundit: No apply button found — skipping.")
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                    return
                self.driver.execute_script("arguments[0].click();", btn[0])
                time.sleep(3)

            # Walk through any follow-up modal steps
            for _ in range(5):
                submit = self.driver.find_elements(By.XPATH,
                    "//button[contains(text(),'Submit') or contains(text(),'Apply') or contains(text(),'Confirm')]")
                if submit:
                    self.driver.execute_script("arguments[0].click();", submit[0])
                    time.sleep(2)
                    break
                nxt = self.driver.find_elements(By.XPATH,
                    "//button[contains(text(),'Next') or contains(text(),'Continue')]")
                if nxt:
                    self.driver.execute_script("arguments[0].click();", nxt[0])
                    time.sleep(2)
                else:
                    break

            self.applied_ids.add(job["job_id"])
            self.applied_count += 1
            self._save_applied(job)
            self.logger.info(f"Foundit: ✓ Applied to '{job['title']}' @ {job['company']}")
        except Exception as e:
            self.logger.error(f"Foundit apply error: {e}")
        finally:
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])

    def _save_applied(self, job: Dict):
        data = _load_json(APPLIED_FILE, {})
        data[job["job_id"]] = {
            "title": job["title"], "company": job["company"],
            "timestamp": datetime.now().isoformat()
        }
        _save_json(APPLIED_FILE, data)
