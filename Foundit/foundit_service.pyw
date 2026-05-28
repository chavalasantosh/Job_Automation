"""
Foundit Full Automation Service (.pyw)
======================================
Runs SILENTLY in the background.
Phase A: Pulse (4h), Phase C: Smart Apply (Daily window)
"""

import time
import os
import sys
import logging
import importlib
from datetime import datetime
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

LOG_FILE = os.path.join(BASE_DIR, "foundit_update.log")
LOCK_FILE = os.path.join(BASE_DIR, "foundit_service.lock")

logger = logging.getLogger("foundit_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2, encoding='utf-8')
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)

def acquire_lock():
    if os.path.exists(LOCK_FILE): return False
    with open(LOCK_FILE, 'w') as f: f.write(str(os.getpid()))
    return True

def release_lock():
    try:
        if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
    except: pass

def main():
    if not acquire_lock(): return
    logger.info("Foundit Automation Service STARTED")
    
    last_pulse = 0
    try:
        while True:
            now = time.time()
            now_dt = datetime.now()
            
            # Phase A: Pulse every 4h
            if now - last_pulse > 4 * 3600:
                logger.info("Executing Phase A: Foundit Pulse")
                try:
                    from foundit_auto_login import refresh_auth
                    if refresh_auth():
                        from foundit_update_manager import update_foundit_headline
                        from foundit_resume_uploader import upload_foundit_resume
                        update_foundit_headline()
                        upload_foundit_resume()
                        last_pulse = now
                except Exception as e:
                    logger.error(f"Pulse failed: {e}")
                    last_pulse = now - 3600 # retry in 1h

            # Phase C: Smart Apply (10 AM - 1 PM)
            today = now_dt.strftime("%Y-%m-%d")
            state_file = os.path.join(BASE_DIR, ".last_apply_date")
            last_apply = ""
            if os.path.exists(state_file):
                with open(state_file, 'r') as f: last_apply = f.read().strip()
            
            if 10 <= now_dt.hour < 13 and today != last_apply:
                logger.info("Executing Phase C: Foundit Smart Apply")
                try:
                    from foundit_auto_apply import run_auto_apply
                    run_auto_apply()
                    with open(state_file, 'w') as f: f.write(today)
                except Exception as e:
                    logger.error(f"Apply failed: {e}")
            
            time.sleep(60)
    except: pass
    finally: release_lock()

if __name__ == "__main__":
    main()
