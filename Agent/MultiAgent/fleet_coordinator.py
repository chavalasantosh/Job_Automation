"""
Fleet Coordinator - FIXED v3
============================
Manages 5 portal agents in parallel daemon threads.
Fixes:
  - Agents now have act(action, state) signature — coordinator calls run_cycle() which handles internally
  - Added exponential backoff on repeated failures
  - Human-like random delay between cycles (8-20s)
  - Clean shutdown on KeyboardInterrupt
"""

import logging
import threading
import time
import random
from typing import List

logger = logging.getLogger("FleetCoordinator")


class FleetCoordinator:
    def __init__(self):
        self.agents = []
        self.threads: List[threading.Thread] = []
        self.is_running = False
        self._setup_logging()

    def _setup_logging(self):
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('*** [FLEET] %(levelname)s - %(message)s ***'))
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def register_agent(self, agent):
        """Adds a specialist agent to the fleet."""
        self.agents.append(agent)
        logger.info(f"Sub-Agent Registered: {agent.portal_name}")

    def start_mission(self, max_total_apps: int = 50):
        """Launches all registered agents in parallel daemon threads."""
        logger.info(f"LAUNCHING MULTI-AGENT MISSION | Goal: {max_total_apps} apps | Agents: {len(self.agents)}")
        self.is_running = True

        for agent in self.agents:
            t = threading.Thread(
                target=self._agent_loop,
                args=(agent,),
                name=f"Agent-{agent.portal_name}",
                daemon=True
            )
            t.start()
            self.threads.append(t)
            logger.info(f"Thread started for: {agent.portal_name}")

        # Block main thread until KeyboardInterrupt or all threads finish
        try:
            while self.is_running and any(t.is_alive() for t in self.threads):
                time.sleep(2)
        except KeyboardInterrupt:
            self.stop_mission()

    def _agent_loop(self, agent):
        """Continuous synchronous execution loop for a sub-agent."""
        logger.info(f"[{agent.portal_name}] Agent is now ACTIVE.")
        consecutive_errors = 0
        while self.is_running and getattr(agent, 'is_active', True):
            try:
                agent.run_cycle()
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[{agent.portal_name}] Cycle error #{consecutive_errors}: {e}")
                # Exponential backoff on repeated failures, capped at 5 min
                backoff = min(30 * (2 ** consecutive_errors), 300)
                time.sleep(backoff)
                continue
            # Human-like delay between cycles
            time.sleep(random.uniform(8, 20))

        logger.info(f"[{agent.portal_name}] Agent loop exited.")

    def stop_mission(self):
        """Gracefully stops all agents."""
        logger.warning("STOPPING ALL AGENTS...")
        self.is_running = False
        for agent in self.agents:
            agent.is_active = False


if __name__ == "__main__":
    coordinator = FleetCoordinator()
    print("Fleet Coordinator ready.")
