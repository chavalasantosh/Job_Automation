import asyncio
import logging
from typing import Dict, Any
from Agent.SingleAgent.base_agent import BasePortalAgent
from NowCurry.models import Job

logger = logging.getLogger(__name__)

class IndeedInfinityAgent(BasePortalAgent):
    """
    Industrial Vision-Language-Action (VLA) agent for Indeed.
    Handles 'Indeed Apply' and screening questions via Career Graph reasoning.
    """
    
    def __init__(self, worker_id: str = None):
        super().__init__(portal_name="Indeed", worker_id=worker_id)
        self.base_url = "https://www.indeed.com"

    async def execute_mission(self, mission_data: Dict[str, Any]):
        """Executes the Indeed Job Mission using the standardized VLA protocol."""
        job_obj = mission_data['job']
        try:
            self._update_status("MISSION_START", mission_id=job_obj.id)
            
            # 1. Navigation
            await self.page.goto(job_obj.url, wait_until="networkidle")
            await self.capture_telemetry()
            
            # 2. Semantic Detection of 'Apply Now'
            analysis = await self.observe_vision("Locate the 'Apply Now' or 'Apply on Company Site' button.")
            
            if "Apply Now" in analysis.get('element', '') and 'selector' in analysis:
                logger.info(f"Indeed Infinity: detected target via selector: {analysis['selector']}")
                await self.click_semantic(analysis['selector'])
                await asyncio.sleep(3)
                await self.capture_telemetry()
                
                # 3. Handle Indeed Multi-page Dialogs semantically
                for step in range(10):
                    dialog = await self.observe_vision("Identify the next step: 'Continue', 'Submit', or a question.")
                    
                    if "Submit" in dialog.get('element', '') and 'selector' in dialog:
                        await self.click_semantic(dialog['selector'])
                        await self.capture_telemetry()
                        break
                    elif "Continue" in dialog.get('element', '') and 'selector' in dialog:
                        await self.click_semantic(dialog['selector'])
                        await asyncio.sleep(2)
                        await self.capture_telemetry()
                    elif "question" in dialog.get('element', '').lower() and 'selector' in dialog:
                        answer = self.solve_screen(dialog['element'])
                        await self.page.fill(dialog['selector'], answer)
                        await self.capture_telemetry()
                
                self.report_application(job_obj, status="SUCCESS")
                self._update_status("MISSION_COMPLETE")
            else:
                self.report_application(job_obj, status="SKIPPED", error="No Indeed Apply found")
                self._update_status("MISSION_COMPLETE")

        except Exception as e:
            logger.error(f"Indeed Infinity Failure: {e}")
            self.report_application(job_obj, status="FAILED", error=str(e))
            self._update_status("MISSION_ERROR")
