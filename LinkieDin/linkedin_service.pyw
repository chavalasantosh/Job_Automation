"""
LinkedIn Full Automation Service (.pyw)
========================================
Runs SILENTLY in the background with NO console window.

Strategic Schedule:
  Phase A — Profile Pulse (every 4h): Headline rotation + resume upload
  Phase C — Smart Apply (daily 10 AM - 1 PM): Apply to freshest jobs
"""

import time
import os
import sys
import logging
import importlib
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Ensure we can find our modules
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

LOG_FILE = os.path.join(BASE_DIR, "linkedin_update.log")
LOCK_FILE = os.path.join(BASE_DIR, "linkedin_service.lock")

# Configure rotating logging
logger = logging.getLogger("linkedin_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    rfh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(rfh)

def acquire_lock():
    """Prevent multiple instances from running."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Check if process is still running (Windows specific)
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, 0, old_pid)
            if handle:
                kernel32.CloseHandle(handle)
                logger.warning(f"Another instance (PID {old_pid}) is already running. Exiting.")
                return False
        except (ValueError, OSError):
            pass

    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass

# --- Phase Functions ---

def refresh_auth():
    try:
        if 'linkedin_auto_login' in sys.modules:
            importlib.reload(sys.modules['linkedin_auto_login'])
        from linkedin_auto_login import refresh_auth as sync_auth
        return sync_auth()
    except Exception as e:
        logger.error(f"Auth refresh failed: {e}", exc_info=True)
        return False

def do_profile_pulse():
    logger.info("--- [PROFILE PULSE] Rotating headline ---")
    try:
        if 'linkedin_update_manager' in sys.modules:
            importlib.reload(sys.modules['linkedin_update_manager'])
        from linkedin_update_manager import update_linkedin_headline
        update_linkedin_headline()
    except Exception as e:
        logger.error(f"Headline update failed: {e}")

    logger.info("--- [PROFILE PULSE] Re-uploading resume ---")
    try:
        if 'linkedin_resume_uploader' in sys.modules:
            importlib.reload(sys.modules['linkedin_resume_uploader'])
        from linkedin_resume_uploader import upload_linkedin_resume
        upload_linkedin_resume()
    except Exception as e:
        logger.error(f"Resume upload failed: {e}")

def do_smart_apply():
    logger.info("--- [SMART APPLY] Starting job applications ---")
    try:
        if 'linkedin_auto_apply' in sys.modules:
            importlib.reload(sys.modules['linkedin_auto_apply'])
        from linkedin_auto_apply import run_auto_apply
        run_auto_apply()
    except Exception as e:
        logger.error(f"Auto-apply failed: {e}")

import json

STATE_FILE = os.path.join(BASE_DIR, ".daily_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"last_profile_date": "", "last_apply_date": ""}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

# --- Main Service Loop ---
def main():
    if not acquire_lock():
        return

    logger.info("=" * 60)
    logger.info("LinkieDin Strategic Automation Service STARTED (PID: %d)", os.getpid())
    logger.info("  Boot Logic: Executes missing daily tasks at/after 9 AM")
    logger.info("  Continuous Polling: Every 15 mins for new job drops")
    logger.info("=" * 60)

    TICK_INTERVAL = 60           # Check every minute
    POLL_INTERVAL = 15 * 60      # 15 minutes continuous poll
    last_continuous_poll = 0
    state = load_state()
    
    try:
        while True:
            now = time.time()
            now_dt = datetime.now()
            current_hour = now_dt.hour
            today_str = now_dt.strftime("%Y-%m-%d")
            
            auth_ok = None # Lazy

            # 1. Daily Boot & Catch-up (Between 9 AM and 23:59 PM)
            if current_hour >= 9:
                dirty = False
                
                # 1a. Daily Profile Pulse
                if state.get("last_profile_date") != today_str:
                    logger.info("═" * 50)
                    logger.info("  EXECUTING DAILY BATCH: PROFILE PULSE")
                    logger.info("═" * 50)
                    auth_ok = auth_ok if auth_ok is not None else refresh_auth()
                    if auth_ok:
                        do_profile_pulse()
                        state["last_profile_date"] = today_str
                        dirty = True
                    else:
                        logger.error("[DAILY BATCH] Auth failed, waiting for next tick...")

                # 1b. Daily Broad Job Sweep
                if state.get("last_apply_date") != today_str:
                    logger.info("═" * 50)
                    logger.info("  EXECUTING DAILY BATCH: SMART APPLY SWEEP")
                    logger.info("═" * 50)
                    auth_ok = auth_ok if auth_ok is not None else refresh_auth()
                    if auth_ok:
                        try:
                            if 'linkedin_auto_apply' in sys.modules:
                                importlib.reload(sys.modules['linkedin_auto_apply'])
                            from linkedin_auto_apply import run_auto_apply
                            run_auto_apply(dry_run=False, continuous_mode=False)
                            state["last_apply_date"] = today_str
                            dirty = True
                        except Exception as e:
                            logger.error(f"Auto-apply sweep failed: {e}")
                
                if dirty:
                    save_state(state)

            # 2. Continuous Polling 
            if state.get("last_apply_date") == today_str:
                if now - last_continuous_poll >= POLL_INTERVAL:
                    logger.info("═" * 50)
                    logger.info("  CONTINUOUS POLL: Checking for fresh jobs (15m tick)")
                    logger.info("═" * 50)
                    auth_ok = auth_ok if auth_ok is not None else refresh_auth()
                    if auth_ok:
                        try:
                            if 'linkedin_auto_apply' in sys.modules:
                                importlib.reload(sys.modules['linkedin_auto_apply'])
                            from linkedin_auto_apply import run_auto_apply
                            run_auto_apply(dry_run=False, continuous_mode=True)
                        except Exception as e:
                            logger.error(f"Continuous auto-apply failed: {e}")
                        last_continuous_poll = now
                    else:
                        last_continuous_poll = now - POLL_INTERVAL + 120 

            time.sleep(TICK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as e:
        logger.error(f"Service crashed: {e}", exc_info=True)
    finally:
        release_lock()
        logger.info("LinkieDin Automation Service STOPPED.")

if __name__ == "__main__":
    main()
