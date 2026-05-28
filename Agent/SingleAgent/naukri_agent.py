"""
Naukri Agent - FIXED v3
========================
Fixes:
  1. act() no longer calls observe() twice — state passed through from run_cycle
  2. URL uses correct Naukri job search format with keyword + location
  3. Added WebDriverWait fallback for slow Naukri SRP loads
  4. Wider card selectors cover both old and new Naukri DOM
  5. apply_btn selector expanded to catch Naukri's varied Apply button markup
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
CONFIG_FILE = os.path.join(ROOT_DIR, "NowCurry", "config.json")
COOKIES_FILE= os.path.join(ROOT_DIR, "NowCurry", "naukri_bot_auth.json")
APPLIED_FILE= os.path.join(ROOT_DIR, "NowCurry", "applied_jobs.json")
DEBUG_FILE  = os.path.join(ROOT_DIR, "NowCurry", "debug_page.html")

CARD_CSS = (
    ".srp-jobtuple-wrapper, "
    "article.jobTuple, "
    "[class*='job-tuple'], "
    "[class*='jobTupleHeader'], "
    ".cust-job-tuple"
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


class NaukriAgent(BasePortalAgent):
    def __init__(self, driver):
        super().__init__(portal_name="Naukri", driver=driver)
        self.config      = _load_json(CONFIG_FILE, {})
        self.keywords    = self.config.get("preferences", {}).get("job_titles", ["Generative AI Engineer"])
        self.location    = self.config.get("preferences", {}).get("location", "Bangalore")
        self.max_apps    = self.config.get("application", {}).get("max_applications_per_run", 50)
        self.applied_ids = set(_load_json(APPLIED_FILE, {}).keys())
        self._cookies_injected = False
        self._kw_index   = 0

    def _inject_cookies(self):
        auth = _load_json(COOKIES_FILE, {})
        cookies = []
        if isinstance(auth, list):
            cookies = auth
        elif isinstance(auth, dict):
            if "cookies" in auth:
                cookies = auth["cookies"]
            elif "cookie" in auth:
                # Parse raw header string "key=value; key2=value2"
                raw_cookie_str = auth["cookie"]
                for pair in raw_cookie_str.split(";"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        cookies.append({
                            "name": k.strip(),
                            "value": v.strip(),
                            "domain": ".naukri.com",
                            "path": "/"
                        })

        if not cookies:
            self.logger.warning(
                "Naukri: No cookies found at NowCurry/naukri_bot_auth.json. "
                "Export Naukri cookies and save as a JSON array to that file."
            )
            return False
        self.driver.get("https://www.naukri.com")
        time.sleep(3)
        injected = 0
        for c in cookies:
            try:
                self.driver.add_cookie({
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", ".naukri.com"),
                    "path":   c.get("path", "/"),
                })
                injected += 1
            except Exception as e:
                self.logger.debug(f"Cookie skip ({c.get('name','')}): {e}")
        self.driver.refresh()
        time.sleep(4)
        self._cookies_injected = True
        self.logger.info(f"Naukri: {injected} cookies injected.")
        return True

    def run_cycle(self):
        if self.applied_count >= self.max_apps:
            self.logger.info(f"Naukri: Limit reached ({self.max_apps}). Cooling down.")
            self.is_active = False
            return

        if not self._cookies_injected:
            if not self._inject_cookies():
                time.sleep(120)
                return

        keyword = self.keywords[self._kw_index % len(self.keywords)]
        self._kw_index += 1

        # FIXED: Proper Naukri search URL
        kw_slug = keyword.lower().replace(" ", "-")
        loc_slug = self.location.lower().replace(" ", "-")
        url = f"https://www.naukri.com/{kw_slug}-jobs-in-{loc_slug}"
        self.logger.info(f"Naukri: Searching '{keyword}' in {self.location}...")
        try:
            self.driver.get(url)
            # Naukri SRP sometimes loads slowly — give it time then wait for cards
            time.sleep(6)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, CARD_CSS.split(",")[0].strip()))
                )
            except TimeoutException:
                pass  # proceed anyway with whatever DOM is available
        except Exception as e:
            self.logger.warning(f"Naukri: Page load failed: {e}")
            return

        # FIX: Single observe pass
        state = self.observe()
        action = self.think(state)
        self.act(action, state)

    def observe(self) -> Dict[str, Any]:
        state = {"type": "SEARCH_PAGE", "jobs": []}

        # Check for chatbot overlay first
        if self.driver.find_elements(By.CSS_SELECTOR,
                ".chatbot-container, .bot-overlay, [class*='chatbot']"):
            q_els = self.driver.find_elements(By.CSS_SELECTOR,
                "[class*='bot-question'], [class*='botQuestion']")
            return {
                "type": "CHATBOT",
                "question": q_els[-1].text if q_els else ""
            }

        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_CSS)
            self.logger.info(f"Naukri: DOM cards found: {len(cards)}")
            if not cards:
                with open(DEBUG_FILE, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source[:80000])
                self.logger.warning(f"Naukri: 0 cards. Page dumped → {DEBUG_FILE}")

            jobs = []
            for card in cards:
                try:
                    job_id = (card.get_attribute("data-job-id") or
                              card.get_attribute("data-id") or
                              card.get_attribute("id"))
                    title_el = card.find_elements(By.CSS_SELECTOR,
                        ".title, .jobTitle, a.title, [class*='jobTitle']")
                    comp_el  = card.find_elements(By.CSS_SELECTOR,
                        ".companyInfo, .company-name, [class*='companyName']")
                    if not job_id and title_el:
                        job_id = title_el[0].text.strip()
                    if job_id and job_id not in self.applied_ids:
                        jobs.append({
                            "job_id":  job_id,
                            "title":   title_el[0].text.strip() if title_el else "Naukri Job",
                            "company": comp_el[0].text.strip() if comp_el else "Company",
                            "card":    card
                        })
                except Exception:
                    continue
            state["jobs"] = jobs
            self.logger.info(f"Naukri: Observed {len(jobs)} new jobs.")
        except Exception as e:
            self.logger.error(f"Naukri observe error: {e}")
        return state

    def think(self, state: Dict[str, Any]) -> str:
        if state["type"] == "CHATBOT":
            return "SOLVE_CHATBOT"
        if state.get("jobs"):
            return "APPLY_JOBS"
        return "IDLE"

    # FIX: act() uses passed-in state — no redundant second observe()
    def act(self, action: str, state: Dict[str, Any] = None):
        self.logger.info(f"Naukri Action: {action}")

        if action == "SOLVE_CHATBOT" and state:
            try:
                question = state.get("question", "Tell me about yourself")
                answer = self.solve_screening_question(question)
                inp = self.driver.find_element(By.CSS_SELECTOR,
                    "input[class*='bot-input'], textarea[class*='bot']")
                inp.clear()
                inp.send_keys(answer)
                send = self.driver.find_element(By.CSS_SELECTOR,
                    "button[class*='bot-send'], button[class*='botSend']")
                self.driver.execute_script("arguments[0].click();", send)
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"Naukri chatbot error: {e}")

        elif action == "APPLY_JOBS" and state:
            for job in state.get("jobs", []):
                if self.applied_count >= self.max_apps:
                    break
                self._apply_to_job(job)
                time.sleep(random.uniform(6, 12))

    def _apply_to_job(self, job: Dict):
        try:
            link_el = job["card"].find_elements(By.CSS_SELECTOR,
                "a.title, a.jobTitle, [class*='jobTitle'] a")
            if not link_el:
                return
            self.driver.execute_script("arguments[0].click();", link_el[0])
            time.sleep(3)
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])

            apply_btn = self.driver.find_elements(By.CSS_SELECTOR,
                "button#apply-button, "
                "button[class*='apply-button'], "
                "button[class*='applyButton'], "
                ".apply-button, "
                "button[class*='apply']")
            if not apply_btn:
                self.logger.info(f"Naukri: No apply button for '{job['title']}' — skipping.")
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                return

            self.driver.execute_script("arguments[0].click();", apply_btn[0])
            time.sleep(3)
            self._handle_apply_modal()
            self.applied_ids.add(job["job_id"])
            self.applied_count += 1
            self._save_applied(job)
            self.logger.info(f"Naukri: ✓ Applied to '{job['title']}' @ {job['company']}")
        except Exception as e:
            self.logger.error(f"Naukri apply error: {e}")
        finally:
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])

    def _handle_apply_modal(self):
        for _ in range(10):
            time.sleep(2)
            try:
                fields = self.driver.find_elements(By.CSS_SELECTOR,
                    "input[type='text']:not([value]), textarea")
                for field in fields:
                    if not field.get_attribute("value"):
                        label_els = self.driver.find_elements(By.XPATH,
                            f"//label[@for='{field.get_attribute('id')}']")
                        label = label_els[0].text if label_els else "Experience"
                        field.send_keys(self.solve_screening_question(label))
            except Exception:
                pass
            submit = self.driver.find_elements(By.XPATH,
                "//button[contains(text(),'Submit') or contains(text(),'Apply') or contains(text(),'Confirm')]")
            if submit:
                self.driver.execute_script("arguments[0].click();", submit[0])
                return

    def _save_applied(self, job: Dict):
        data = _load_json(APPLIED_FILE, {})
        data[job["job_id"]] = {
            "title": job["title"], "company": job["company"],
            "timestamp": datetime.now().isoformat()
        }
        _save_json(APPLIED_FILE, data)
