import os
import sys
import json
import logging
import asyncio
import subprocess
import time
import socket
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="NowCurry Fleet Command Center")

PORTALS = {
    "Naukri": {"port": 8000, "url": "http://localhost:8000", "path": "NowCurry/web_server.py"},
    "LinkedIn": {"port": 8001, "url": "http://localhost:8001", "path": "LinkieDin/web_server.py"},
    "Foundit": {"port": 8002, "url": "http://localhost:8002", "path": "Foundit/web_server.py"},
    "Glassdoor": {"port": 8003, "url": "http://localhost:8003", "path": "GallasuDooru/web_server.py"},
    "Indeed": {"port": 8004, "url": "http://localhost:8004", "path": "InDeed/web_server.py"}
}

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

@app.get("/")
async def get_master_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "fleet_dashboard.html"))

@app.get("/api/status")
async def get_fleet_status():
    status = {}
    for name, info in PORTALS.items():
        status[name] = {
            "online": is_port_open(info['port']),
            "url": info['url'],
            "port": info['port']
        }
    return status

@app.post("/api/launch-all")
async def launch_all_servers(background_tasks: BackgroundTasks):
    """Attempt to start all dash web servers in background."""
    def start_servers():
        python_exe = sys.executable
        for name, info in PORTALS.items():
            if not is_port_open(info['port']):
                server_path = os.path.join(BASE_DIR, info['path'])
                if os.path.exists(server_path):
                    # Start as detached background process
                    subprocess.Popen([python_exe, server_path], 
                                     creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS)
                    time.sleep(1)

    background_tasks.add_task(start_servers)
    return {"message": "Launch command sent to all portals"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7999)
