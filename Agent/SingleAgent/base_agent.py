"""
Base Portal Agent - NowCurry Infinity Edition
=============================================
Unified base for both Selenium and Playwright agents.
Provides: Observe -> Think -> Act lifecycle, DB heartbeat, RAG integration.
"""

import os
import sys
import time
import datetime
import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# Standardized root-relative path resolution
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from RAG.SingleRAG.career_graph import CareerGraph

logger = logging.getLogger(__name__)


class BasePortalAgent(ABC):
    """
    Unified Base for all NowCurry Agents.
    Supports both Selenium (simple agents) and Playwright (infinity agents).
    """

    def __init__(self, portal_name: str, driver=None, worker_id: Optional[str] = None):
        self.portal_name = portal_name
        self.driver = driver  # Selenium driver (for simple agents)
        self.worker_id = worker_id or f"node_{os.getpid()}"
        self.proxy_ip = os.environ.get("PROXY_IP", "direct")
        self.relay_url = os.environ.get("RELAY_URL", "http://localhost:8000")

        # RAG Brain — shared across all agents
        self.graph = CareerGraph()

        # Playwright state (used by Infinity agents only)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

        # Agent lifecycle state
        self.is_active = True
        self.applied_count = 0

        # Per-agent logger (used by specialist agents via self.logger)
        self.logger = logging.getLogger(f"Agent.{portal_name}")
        if not self.logger.handlers:
            _h = logging.StreamHandler()
            _h.setFormatter(logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'))
            self.logger.addHandler(_h)
        self.logger.setLevel(logging.INFO)

        self._update_status("INITIALIZING")

    # ──────────────────────────────────────────────
    # ABSTRACT INTERFACE (Agent-Specific)
    # ──────────────────────────────────────────────

    def observe(self) -> Dict[str, Any]:
        """Scans current page state. Override in specialist agents."""
        return {}

    def think(self, state: Dict[str, Any]) -> str:
        """Decides next action from state. Override in specialist agents."""
        return "IDLE"

    def act(self, action: str):
        """Executes the decided action. Override in specialist agents."""
        pass

    def run_cycle(self):
        """Standard synchronous Agent Cycle: Observe -> Think -> Act."""
        try:
            state = self.observe()
            action = self.think(state)
            self.act(action)
        except Exception as e:
            logger.error(f"[{self.portal_name}] Cycle error: {e}")
            time.sleep(5)

    # ──────────────────────────────────────────────
    # SHARED INTELLIGENCE
    # ──────────────────────────────────────────────

    def solve_screening_question(self, question: str) -> str:
        """Solves career screening questions using the local CareerGraph + Gemma."""
        logger.info(f"[{self.portal_name}] Solving: {question}")
        return self.graph.solve_question(question)

    # ──────────────────────────────────────────────
    # DATABASE HEARTBEAT (uses NowCurry DB)
    # ──────────────────────────────────────────────

    def _update_status(self, status: str, mission_id: Optional[str] = None):
        """Logs status. Attempts DB write if available, silently skips if not."""
        logger.info(f"[{self.portal_name}][{self.worker_id}] Status: {status}" +
                    (f" | Mission: {mission_id}" if mission_id else ""))
        try:
            from NowCurry.database import SessionLocal
            from NowCurry.models import AgentStatus
            db = SessionLocal()
            try:
                agent = db.query(AgentStatus).filter(AgentStatus.id == self.worker_id).first()
                if not agent:
                    agent = AgentStatus(id=self.worker_id, portal=self.portal_name)
                    db.add(agent)
                agent.status = status
                if mission_id:
                    agent.current_mission = mission_id
                agent.last_heartbeat = datetime.datetime.utcnow()
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Heartbeat DB write skipped: {e}")

    def report_application(self, job_obj, status: str = "APPLIED", error: str = None):
        """Logs an application to the DB."""
        try:
            from NowCurry.database import SessionLocal
            from NowCurry.models import Job, Application
            db = SessionLocal()
            try:
                existing = db.query(Job).filter(Job.id == job_obj.id).first()
                if not existing:
                    db.add(job_obj)
                    db.commit()
                app = Application(
                    job_id=job_obj.id,
                    status=status,
                    error_log=error,
                    worker_id=self.worker_id,
                    proxy_ip=self.proxy_ip,
                    applied_at=datetime.datetime.utcnow()
                )
                db.add(app)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Application log failed: {e}")

    # ──────────────────────────────────────────────
    # PLAYWRIGHT STEALTH LAYER (Infinity agents)
    # ──────────────────────────────────────────────

    async def launch_stealth_browser(self, playwright_instance, headless: bool = True):
        """Launches a stealth Playwright browser."""
        self.playwright = playwright_instance
        try:
            from NowCurry.stealth_factory import StealthFactory
            profile = StealthFactory.generate_profile()
        except Exception:
            profile = {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "viewport": {"width": 1920, "height": 1080},
                "deviceScaleFactor": 1
            }

        try:
            self.browser = await self.playwright.chromium.launch(headless=headless)
        except Exception as e:
            logger.warning(f"Playwright launch failed ({e}), trying system Chrome...")
            self.browser = await self.playwright.chromium.launch(headless=headless, channel="chrome")

        self.context = await self.browser.new_context(
            user_agent=profile['userAgent'],
            viewport=profile['viewport'],
            device_scale_factor=profile['deviceScaleFactor'],
            has_touch=True
        )

        try:
            from NowCurry.stealth_factory import StealthFactory
            await self.context.add_init_script(StealthFactory.get_stealth_scripts())
        except Exception:
            pass

        self.page = await self.context.new_page()
        self._update_status("BROWSER_READY")
        return self.page

    async def observe_semantic(self) -> List[Dict[str, Any]]:
        """Extracts interactive DOM map for LLM reasoning."""
        if not self.page:
            return []
        selector = "button, a, input, select, textarea, [role='button'], [role='link']"
        elements = await self.page.query_selector_all(selector)
        semantic_map = []
        for el in elements:
            try:
                if await el.is_visible():
                    semantic_map.append({
                        "tag": await el.evaluate("node => node.tagName"),
                        "text": (await el.inner_text())[:50].strip(),
                        "aria": await el.get_attribute("aria-label"),
                        "placeholder": await el.get_attribute("placeholder"),
                        "role": await el.get_attribute("role"),
                        "id": await el.get_attribute("id")
                    })
            except:
                continue
        return semantic_map[:20]

    async def observe_vision(self, objective: str) -> Dict[str, Any]:
        """Semantic DOM reasoning via local VisionActuator."""
        elements = await self.observe_semantic()
        try:
            from NowCurry.vision_actuator import VisionActuator
            return VisionActuator().analyze_semantic_dom(elements, objective)
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {}

    async def capture_telemetry(self):
        """Screenshots current page and relays to Command Center."""
        if not self.page:
            return
        import tempfile
        path = os.path.join(tempfile.gettempdir(), f"{self.worker_id}_latest.png")
        try:
            await self.page.screenshot(path=path)
            with open(path, "rb") as f:
                requests.post(
                    f"{self.relay_url}/relay/screenshot/{self.worker_id}",
                    files={"file": f}, timeout=5
                )
        except Exception as e:
            logger.debug(f"Telemetry skipped: {e}")

    async def click_semantic(self, selector: str):
        """Human-like click with mouse movement."""
        if not self.page:
            return
        try:
            box = await self.page.locator(selector).bounding_box()
            if box:
                x = box['x'] + box['width'] / 2
                y = box['y'] + box['height'] / 2
                await self.page.mouse.move(x, y, steps=10)
            await self.page.click(selector)
        except Exception as e:
            logger.error(f"Semantic click failed ({selector}): {e}")

    async def execute_mission(self, mission_data: Dict[str, Any]):
        """Override in Infinity agents for Playwright-based missions."""
        pass

    async def close(self):
        """Graceful cleanup."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
