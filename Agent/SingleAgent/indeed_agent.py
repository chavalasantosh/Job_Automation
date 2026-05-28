"""
Indeed Agent - FIXED v3
========================
Fixes:
  1. act() no longer calls observe() twice — state passed through from run_cycle
  2. URL corrected: indeed.com/jobs (not in.indeed.com which redirects)
  3. Card selectors widened to catch tapItem, mosaic-provider, result containers
  4. job_id now pulled from data-jk on card OR linked anchor — with fallback
  5. Debug dump goes to InDeed/ folder
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
CONFIG_FILE = os.path.join(ROOT_DIR, "InDeed", "config.json")
COOKIES_FILE= os.path.join(ROOT_DIR, "InDeed", "indeed_cookies.json")
APPLIED_FILE= os.path.join(ROOT_DIR, "InDeed", "applied_jobs.json")
DEBUG_FILE  = os.path.join(ROOT_DIR, "InDeed", "debug_page.html")

CARD_CSS = (
    ".job_seen_beacon, "
    ".tapItem, "
    "[class*='mosaic-provider-jobcards'] li, "
    ".result, "
    "[data-jk], "
    "[class*='jobCard']"
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


class IndeedAgent(BasePortalAgent):
    def __init__(self, driver):
        super().__init__(portal_name="Indeed", driver=driver)
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
            self.logger.warning("Indeed: No cookies found. Check indeed_cookies.json.")
            return False
        # Navigate to base domain — use www.indeed.com (not in.)
        self.driver.get("https://www.indeed.com")
        time.sleep(3)
        injected = 0
        for c in cookies:
            try:
                self.driver.add_cookie({
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", ".indeed.com"),
                    "path":   c.get("path", "/"),
                })
                injected += 1
            except Exception as e:
                self.logger.debug(f"Cookie skip ({c.get('name','')}): {e}")
        self.driver.refresh()
        time.sleep(4)
        self._cookies_injected = True
        self.logger.info(f"Indeed: {injected} cookies injected.")
        return True

    def run_cycle(self):
        if self.applied_count >= self.max_apps:
            self.logger.info(f"Indeed: Limit reached ({self.max_apps}). Cooling down.")
            self.is_active = False
            return

        if not self._cookies_injected:
            if not self._inject_cookies():
                time.sleep(60)
                return

        keyword = self.keywords[self._kw_index % len(self.keywords)]
        self._kw_index += 1

        # FIXED: Use indeed.com/jobs — stable across regions
        url = (
            f"https://www.indeed.com/jobs"
            f"?q={keyword.replace(' ', '+')}"
            f"&l={self.location.replace(' ', '+')}"
            f"&fromage=7"
            f"&sort=date"
        )
        self.logger.info(f"Indeed: Searching '{keyword}' in {self.location}...")
        try:
            self.driver.get(url)
            time.sleep(10)
        except Exception as e:
            self.logger.warning(f"Indeed: Page load failed: {e}")
            return

        # FIX: Single observe pass, state passed to act()
        state = self.observe()
        action = self.think(state)
        self.act(action, state)

    def observe(self) -> Dict[str, Any]:
        state = {"type": "SEARCH_PAGE", "jobs": []}
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_CSS)
            self.logger.info(f"Indeed: DOM cards found: {len(cards)}")
            if not cards:
                with open(DEBUG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source[:80000])
                self.logger.warning(f"Indeed: 0 cards. Page dumped → {DEBUG_FILE}")

            jobs = []
            for card in cards:
                try:
                    # Try to get data-jk from card or nested anchor
                    job_id = card.get_attribute("data-jk")
                    if not job_id:
                        links = card.find_elements(By.CSS_SELECTOR, "a[data-jk], a[id*='job_']")
                        if links:
                            job_id = links[0].get_attribute("data-jk") or links[0].get_attribute("id")
                    if not job_id:
                        job_id = card.get_attribute("id")

                    title_el = card.find_elements(By.CSS_SELECTOR,
                        "h2.jobTitle, [class*='jobTitle'], h2 a span, .title")
                    comp_el  = card.find_elements(By.CSS_SELECTOR,
                        "[data-testid='company-name'], .companyName, [class*='companyName']")

                    if job_id and job_id not in self.applied_ids:
                        jobs.append({
                            "job_id":  job_id,
                            "title":   title_el[0].text.strip() if title_el else "Indeed Job",
                            "company": comp_el[0].text.strip() if comp_el else "Company",
                            "card":    card
                        })
                except Exception:
                    continue
            state["jobs"] = jobs
            self.logger.info(f"Indeed: Observed {len(jobs)} new jobs.")
        except Exception as e:
            self.logger.error(f"Indeed observe error: {e}")
        return state

    def think(self, state: Dict[str, Any]) -> str:
        return "APPLY_JOBS" if state.get("jobs") else "IDLE"

    # FIX: act() uses passed-in state — no redundant second observe()
    def act(self, action: str, state: Dict[str, Any] = None):
        self.logger.info(f"Indeed Action: {action}")
        if action == "APPLY_JOBS" and state:
            for job in state.get("jobs", []):
                if self.applied_count >= self.max_apps:
                    break
                self._apply_to_job(job)
                time.sleep(random.uniform(5, 10))

    def _apply_to_job(self, job: Dict):
        original_window = self.driver.current_window_handle
        try:
            link = job["card"].find_elements(By.CSS_SELECTOR,
                "a.jcs-JobTitle, h2 a, a[data-jk]")
            if not link:
                return
            self.driver.execute_script("arguments[0].click();", link[0])
            time.sleep(4)

            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])

            # Look for Indeed Apply button
            apply_btn = self.driver.find_elements(By.CSS_SELECTOR,
                "#indeedApplyButton, [data-indeed-apply-onready], "
                "button[class*='indeedApply'], button[class*='apply']")
            if not apply_btn:
                self.logger.info(f"Indeed: No instant apply for '{job['title']}' — skipping.")
                return

            self.driver.execute_script("arguments[0].click();", apply_btn[0])
            time.sleep(3)

            # Handle the Indeed Apply iframe/modal
            for _ in range(8):
                # Switch into iframe if present
                iframes = self.driver.find_elements(By.CSS_SELECTOR,
                    "iframe[title='Indeed Apply'], iframe[name='indeedapply-modal-iframe']")
                if iframes:
                    try:
                        self.driver.switch_to.frame(iframes[0])
                    except Exception:
                        pass

                # Fill any unfilled text inputs
                try:
                    fields = self.driver.find_elements(By.CSS_SELECTOR,
                        "input[required]:not([value]), textarea")
                    for field in fields:
                        if not field.get_attribute("value"):
                            field.send_keys("3")  # generic years-of-experience default
                except Exception:
                    pass

                # Submit / Continue / Next
                cont = self.driver.find_elements(By.CSS_SELECTOR,
                    "button.ia-continueButton, button[data-testid='ia-continueButton'], "
                    "button[class*='continue'], button[class*='next']")
                if cont:
                    self.driver.execute_script("arguments[0].click();", cont[0])
                    time.sleep(2)
                    self.driver.switch_to.default_content()
                    continue

                # Final submit
                submit = self.driver.find_elements(By.CSS_SELECTOR,
                    "button[class*='submit'], button[type='submit']")
                if submit:
                    self.driver.execute_script("arguments[0].click();", submit[0])
                    time.sleep(2)
                    self.driver.switch_to.default_content()
                    break

                self.driver.switch_to.default_content()
                break

            self.applied_ids.add(job["job_id"])
            self.applied_count += 1
            self._save_applied(job)
            self.logger.info(f"Indeed: ✓ Applied to '{job['title']}' @ {job['company']}")
        except Exception as e:
            self.logger.error(f"Indeed apply error: {e}")
        finally:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(original_window)

    def _save_applied(self, job: Dict):
        data = _load_json(APPLIED_FILE, {})
        data[job["job_id"]] = {
            "title": job["title"], "company": job["company"],
            "timestamp": datetime.now().isoformat()
        }
        _save_json(APPLIED_FILE, data)
