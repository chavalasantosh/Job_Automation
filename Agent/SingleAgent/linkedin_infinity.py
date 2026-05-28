import asyncio
import logging
import json
import os
from typing import Dict, Any, List
from Agent.SingleAgent.base_agent import BasePortalAgent
from NowCurry.models import Job

logger = logging.getLogger(__name__)

class LinkedInInfinityAgent(BasePortalAgent):
    """
    Industrial Vision-Language-Action (VLA) agent for LinkedIn.
    Handles 'Easy Apply' dialogs autonomously using semantic visual reasoning.
    """
    
    def __init__(self, worker_id: str = None):
        super().__init__(portal_name="LinkedIn", worker_id=worker_id)
        self.base_url = "https://www.linkedin.com"
        self.cookies_path = os.path.join(os.path.dirname(__file__), "..", "..", "LinkieDin", "linkedin_cookies.json")

    async def inject_cookies(self):
        """Injects existing Infinity session cookies for LinkedIn."""
        if os.path.exists(self.cookies_path):
            with open(self.cookies_path, 'r') as f:
                cookies = json.load(f)
                # Playwright expects a slightly different cookie format than Selenium exported JSON
                formatted_cookies = []
                for c in cookies:
                    formatted_cookies.append({
                        "name": c['name'],
                        "value": c['value'],
                        "domain": ".linkedin.com",
                        "path": "/",
                        "sameSite": "Lax" # Default for LinkedIn
                    })
                await self.context.add_cookies(formatted_cookies)
            logger.info("LinkedIn Infinity: Injected secure session cookies.")

    async def execute_mission(self, mission_data: Dict[str, Any]):
        """Executes the LinkedIn Job Mission using the standardized VLA protocol."""
        job_obj = mission_data['job']
        try:
            self._update_status("MISSION_START", mission_id=job_obj.id)
            
            # 1. High-Stealth Launch
            await self.inject_cookies()
            await self.page.goto(job_obj.url, wait_until="networkidle")
            await self.capture_telemetry()
            
            # 2. Semantic Detection of Application Path
            analysis = await self.observe_vision("Locate the 'Easy Apply' button.")
            
            if "Easy Apply" in analysis.get('element', '') and 'selector' in analysis:
                logger.info(f"LinkedIn Infinity: detected target via selector: {analysis['selector']}")
                await self.click_semantic(analysis['selector'])
                await asyncio.sleep(2)
                
                # 3. Handle the multi-step dialog semantically
                for step in range(15):
                    dialog = await self.observe_vision("Examine the 'Easy Apply' dialog. Find 'Next', 'Review', or 'Submit'.")
                    
                    if dialog.get('action') == 'click' and 'selector' in dialog:
                        await self.click_semantic(dialog['selector'])
                        await self.capture_telemetry()
                        
                        if dialog.get('element') == 'Submit application':
                            logger.info("LinkedIn Infinity: Application Submitted!")
                            self.report_application(job_obj, status="SUCCESS")
                            self._update_status("MISSION_COMPLETE")
                            return
                        
                        await asyncio.sleep(2)
                    elif "question" in dialog.get('element', '').lower() and 'selector' in dialog:
                        answer = self.solve_screen(dialog['element'])
                        await self.page.fill(dialog['selector'], answer)
                        await self.capture_telemetry()
                    else:
                        # Fallback: check if dialog closed
                        if not await self.page.query_selector(".jobs-easy-apply-modal"):
                            logger.info("LinkedIn Infinity: Dialog closure detected.")
                            self.report_application(job_obj, status="SUCCESS")
                            self._update_status("MISSION_COMPLETE")
                            return
            else:
                logger.warning("LinkedIn Infinity: 'Easy Apply' button not found via Semantic Vision.")
                self.report_application(job_obj, status="SKIPPED", error="No Easy Apply found")

        except Exception as e:
            logger.error(f"LinkedIn VLA Failure: {e}")
            self.report_application(job_obj, status="ERROR", error=str(e))
            self._update_status("MISSION_ERROR")
