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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

app = FastAPI(title="Indeed Automation Enterprise Dashboard")

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATS_FILE = os.path.join(BASE_DIR, "indeed_applied_jobs.json")
LOG_FILE = os.path.join(BASE_DIR, "indeed_update.log")

@app.get("/")
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.get("/api/stats")
async def get_stats():
    try:
        applied_jobs = []
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f: applied_jobs = json.load(f)
        return {
            "total_applied": len(applied_jobs),
            "recent_applications": applied_jobs[-50:][::-1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
async def stream_logs():
    def log_generator():
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 5000), 0)
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
    def run_script():
        try:
            subprocess.run([sys.executable, "indeed_auto_apply.py"], check=True)
        except: pass
    background_tasks.add_task(run_script)
    return {"message": "Automation run started in background"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
