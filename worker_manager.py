import subprocess
import os
import sys
import threading
import time
import queue
import logging
from typing import Dict, Optional
from database import SessionLocal, LogEntry, AgentStatus, engine
import json

class WorkerManager:
    """
    Autonomous Orchestrator for Portal Agents.
    Handles process lifecycles, log aggregation, and self-healing.
    """
    def __init__(self):
        self.workers: Dict[str, subprocess.Popen] = {}
        self.log_queue = queue.Queue()
        self.is_running = True
        self.logger = logging.getLogger("WorkerManager")
        
        # Start the global log processing thread
        self.log_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.log_thread.start()

    def start_worker(self, agent_name: str, script_path: str):
        """Launches an agent in a background process with piped logs."""
        if agent_name in self.workers and self.workers[agent_name].poll() is None:
            self.logger.warning(f"Worker {agent_name} is already running.")
            return

        self.logger.info(f"Initiating Global Launch for Agent: {agent_name}")
        
        # Prepare environment
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))
        env["AGENT_NAME"] = agent_name

        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        self.workers[agent_name] = process
        
        # Spawn dedicated log capturing threads for this process
        threading.Thread(target=self._capture_stream, args=(agent_name, process.stdout, "INFO"), daemon=True).start()
        threading.Thread(target=self._capture_stream, args=(agent_name, process.stderr, "ERROR"), daemon=True).start()
        
        # Update status in DB
        self._update_db_status(agent_name, "ACTIVE")

    def stop_worker(self, agent_name: str):
        """Gracefully terminates a worker process."""
        if agent_name in self.workers:
            process = self.workers[agent_name]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            del self.workers[agent_name]
            self._update_db_status(agent_name, "OFFLINE")
            self.logger.info(f"Worker {agent_name} has been decommissioned.")

    def _capture_stream(self, agent_name: str, stream, level: str):
        """Reads lines from a subprocess stream and pushes to global queue."""
        for line in iter(stream.readline, ''):
            if not self.is_running: break
            clean_line = line.strip()
            if clean_line:
                self.log_queue.put({
                    "agent": agent_name,
                    "level": level,
                    "message": clean_line,
                    "module": "ProcessOutput"
                })
        stream.close()

    def _process_logs(self):
        """Continuously persists logs from the queue to the database."""
        while self.is_running:
            try:
                item = self.log_queue.get(timeout=1)
                db = SessionLocal()
                try:
                    log = LogEntry(
                        agent_name=item["agent"],
                        level=item["level"],
                        message=item["message"],
                        module=item["module"]
                    )
                    db.add(log)
                    db.commit()
                except Exception as e:
                    print(f"FAILED TO PERSIST LOG: {e}")
                finally:
                    db.close()
            except queue.Empty:
                continue

    def _update_db_status(self, agent_name: str, status: str):
        db = SessionLocal()
        try:
            agent = db.query(AgentStatus).filter(AgentStatus.name == agent_name).first()
            if not agent:
                agent = AgentStatus(name=agent_name)
                db.add(agent)
            agent.status = status
            agent.last_seen = time.time() # Or datetime
            db.commit()
        finally:
            db.close()

    def monitor_health(self):
        """Periodic check to ensure workers are still alive; restarts if crashed."""
        for agent_name, process in list(self.workers.items()):
            if process.poll() is not None:
                self.logger.error(f"CRITICAL: Agent {agent_name} has exited unexpectedly.")
                self._update_db_status(agent_name, "CRASHED")
                # TODO: Implement auto-restart logic here based on config

if __name__ == "__main__":
    # Test Stub
    manager = WorkerManager()
    print("Worker Manager Infrastructure ready.")
