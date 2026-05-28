import os
import sys
import json
import logging
import asyncio
import subprocess
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# Add current dir to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

app = FastAPI(title="LinkieDin Automation Enterprise Dashboard")

# Constants
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATS_FILE = os.path.join(BASE_DIR, "linkedin_applied_jobs.json")
RUN_STATS_FILE = os.path.join(BASE_DIR, "linkedin_run_stats.json")
LOG_FILE = os.path.join(BASE_DIR, "linkedin_update.log")

class ConfigUpdate(BaseModel):
    job_titles: List[str]
    location: str
    max_applications_per_run: int
    rate_limit_delay_seconds: int
    dry_run: bool

@app.get("/")
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.get("/api/stats")
async def get_stats():
    """Get all-time applied stats and recent run history."""
    try:
        applied_jobs = []
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                applied_jobs = json.load(f)
        
        runs = []
        if os.path.exists(RUN_STATS_FILE):
            with open(RUN_STATS_FILE, 'r') as f:
                runs = json.load(f)
        
        return {
            "total_applied": len(applied_jobs),
            "recent_applications": applied_jobs[-50:][::-1],
            "run_history": runs[-20:] if isinstance(runs, list) else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    if not os.path.exists(CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Config file not found")
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

@app.post("/api/config")
async def update_config(update: ConfigUpdate):
    """Update configuration."""
    if not os.path.exists(CONFIG_FILE):
        raise HTTPException(status_code=404, detail="Config file not found")
    
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    # Update nested structure
    config['preferences']['job_titles'] = update.job_titles
    config['preferences']['location'] = update.location
    config['application']['max_applications_per_run'] = update.max_applications_per_run
    config['application']['rate_limit_delay_seconds'] = update.rate_limit_delay_seconds
    config['settings']['dry_run'] = update.dry_run
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    
    return {"message": "Config updated successfully"}

@app.get("/api/logs")
async def stream_logs():
    """Stream log file content."""
    def log_generator():
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                # Seek to end-ish
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 10000), 0) # last 10KB
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.5)
                        continue
                    yield line
        else:
            yield "Log file not found."

    return StreamingResponse(log_generator(), media_type="text/plain")

@app.post("/api/run")
async def trigger_run(background_tasks: BackgroundTasks):
    """Trigger the auto-apply script."""
    def run_script():
        try:
            # Run using the same python interpreter
            subprocess.run([sys.executable, "linkedin_auto_apply.py"], check=True)
        except Exception as e:
            logging.error(f"Dashboard run trigger failed: {e}")

    background_tasks.add_task(run_script)
    return {"message": "Automation run started in background"}

if __name__ == "__main__":
    import uvicorn
    # Using 8001 to avoid conflict with Naukri dashboard if both are running
    uvicorn.run(app, host="0.0.0.0", port=8001)
