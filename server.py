import os
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from NowCurry.database import SessionLocal, init_db
from NowCurry.models import AgentStatus, Application, Job

# Global Configuration (Native Windows Pathing)
MISSION_STORAGE = os.path.join(os.getcwd(), "missions")
if not os.path.exists(MISSION_STORAGE):
    os.makedirs(MISSION_STORAGE, exist_ok=True)

app = FastAPI(title="NowCurry Infinity Command Center")

# CORS for React Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Mission Visuals for the "Theater Mode" Dashboard
app.mount("/relay/view", StaticFiles(directory=MISSION_STORAGE), name="missions")

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/")
def read_root():
    return {
        "status": "online",
        "platform": "NowCurry Infinity v2",
        "theater_mode": "/relay/view",
        "message": "Industrial Hive Control Plane is Active."
    }

# --- FLEET MANAGEMENT ---

@app.get("/api/fleet")
def get_fleet_status():
    db = SessionLocal()
    try:
        agents = db.query(AgentStatus).all()
        return agents
    finally:
        db.close()

@app.get("/api/stats")
def get_stats():
    db = SessionLocal()
    try:
        total_apps = db.query(Application).count()
        success_apps = db.query(Application).filter(Application.status == "SUCCESS").count()
        failed_apps = db.query(Application).filter(Application.status == "FAILED").count()
        return {
            "total_applications": total_apps,
            "success_rate": (success_apps / total_apps * 100) if total_apps > 0 else 0,
            "failed": failed_apps
        }
    finally:
        db.close()

# --- VISUAL RELAY (THEATER MODE) ---

@app.post("/relay/screenshot/{worker_id}")
async def relay_screenshot(worker_id: str, file: UploadFile = File(...)):
    """Receives real-time visual telemetry from worker pods."""
    file_path = os.path.join(MISSION_STORAGE, f"{worker_id}_latest.png")
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    return {"status": "success", "worker_id": worker_id}

# --- TELEMETRY STREAM ---

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # In a real environment, this would poll the DB or a Redis stream
            # For the prototype, we send periodic system heartbeats
            heartbeat = {
                "timestamp": datetime.utcnow().isoformat(),
                "agent": "SYSTEM",
                "level": "INFO",
                "message": "Infinity Hive Online | All nodes reporting secure."
            }
            await websocket.send_text(json.dumps([heartbeat]))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
