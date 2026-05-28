import asyncio
import logging
from typing import Dict, Any
from Agent.SingleAgent.base_agent import BasePortalAgent
from NowCurry.models import Job

logger = logging.getLogger(__name__)

class FounditInfinityAgent(BasePortalAgent):
    """
    Industrial Vision-Language-Action (VLA) agent for Foundit.in.
    Specializes in 'Quick Apply' flows and visual dialog handling.
    """
    
    def __init__(self, worker_id: str = None):
        super().__init__(portal_name="Foundit", worker_id=worker_id)
        self.base_url = "https://www.foundit.in"

    async def execute_mission(self, mission_data: Dict[str, Any]):
        """Executes the Foundit Job Mission using the standardized VLA protocol."""
        job_obj = mission_data['job']
        try:
            self._update_status("MISSION_START", mission_id=job_obj.id)
            
            # 1. Navigate to search/job URL
            await self.page.goto(job_obj.url, wait_until="networkidle")
            await self.capture_telemetry()
            
            # 2. Visual Detection of 'Quick Apply'
            analysis = await self.observe_vision("Locate the primary 'Quick Apply' or 'Apply' button.")
            
            if "Apply" in analysis.get('element', '') and 'selector' in analysis:
                logger.info(f"Foundit Infinity: detected target via selector: {analysis['selector']}")
                await self.click_semantic(analysis['selector'])
                await asyncio.sleep(2)
                await self.capture_telemetry()
                
                # 3. Handle Foundit Dialogs (Sequential reasoning)
                for _ in range(5):
                    dialog = await self.observe_vision("Identify any screening questions or 'Submit' buttons.")
                    
                    if "Submit" in dialog.get('element', '') and 'selector' in dialog:
                        await self.click_semantic(dialog['selector'])
                        await self.capture_telemetry()
                        break
                    elif "question" in dialog.get('element', '').lower() and 'selector' in dialog:
                        answer = self.solve_screen(dialog['element'])
                        await self.page.fill(dialog['selector'], answer)
                        await self.capture_telemetry()
                
                self.report_application(job_obj, status="SUCCESS")
                self._update_status("MISSION_COMPLETE")
            else:
                self.report_application(job_obj, status="SKIPPED", error="No Quick Apply found")
                self._update_status("MISSION_COMPLETE")

        except Exception as e:
            logger.error(f"Foundit Infinity Failure: {e}")
            self.report_application(job_obj, status="FAILED", error=str(e))
            self._update_status("MISSION_ERROR")
