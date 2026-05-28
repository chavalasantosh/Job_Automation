"""
10x Master Dispatcher - Omni-Agent Mode (FIXED)
===============================================
Single-window launcher for the entire industrial fleet.
Fixed: Correct agent types, proper sys.path, init_db() before agents start.
"""

import sys
import os
import time
import logging

# ── Root path setup (must come before all local imports) ──
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MasterDispatch")

from Agent.MultiAgent.fleet_coordinator import FleetCoordinator
from Agent.SingleAgent.linkedin_agent import LinkedInAgent
from Agent.SingleAgent.naukri_agent import NaukriAgent
from Agent.SingleAgent.foundit_agent import FounditAgent
from Agent.SingleAgent.glassdoor_agent import GlassdoorAgent
from Agent.SingleAgent.indeed_agent import IndeedAgent


def get_headless_driver(portal_name: str = ""):
    """
    Creates a Selenium driver with stealth anti-bot settings.
    NOTE: Glassdoor & Indeed use Cloudflare IUAM — they require a non-headless
    browser. We run with --window-position=off-screen so the window is invisible
    but still passes Cloudflare's JS fingerprint challenge.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    import tempfile, os

    CLOUDFLARE_PORTALS = {"Glassdoor", "Indeed", "LinkedIn"}

    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    if portal_name in CLOUDFLARE_PORTALS:
        # Non-headless but off-screen so user doesn't see 5 windows
        opts.add_argument("--window-position=-2400,-2400")
        logger.info(f"{portal_name}: Using visible (off-screen) browser to bypass Cloudflare.")
    else:
        opts.add_argument("--headless=new")

    # Unique temp profile per agent to avoid profile lock conflicts
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"nowcurry_{portal_name.lower()}_")
        opts.add_argument(f"--user-data-dir={temp_dir}")
    except Exception:
        pass

    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # Try Brave first, fall back to Chrome
    brave_path = os.path.join(
        os.path.expanduser("~"), "AppData", "Local",
        "BraveSoftware", "Brave-Browser", "Application", "brave.exe"
    )
    if os.path.exists(brave_path):
        opts.binary_location = brave_path

    return webdriver.Chrome(options=opts)



def launch_omni_agent_fleet():
    print("=" * 55)
    print("   NOWCURRY OMNI-AGENT FLEET — SINGLE WINDOW MODE")
    print("=" * 55)

    # FIX: Initialize DB BEFORE any agent (agents write heartbeats on init)
    try:
        from NowCurry.database import init_db
        init_db()
        logger.info("State Layer (SQLite) initialized.")
    except Exception as e:
        logger.warning(f"DB init skipped (not critical for simple agents): {e}")

    coordinator = FleetCoordinator()

    # FIX: Simple agents use Selenium driver — Infinity agents use Playwright
    # This dispatcher uses Simple Agents (no Playwright dependency)
    agent_classes = [
        (LinkedInAgent, "LinkedIn"),
        (NaukriAgent, "Naukri"),
        (FounditAgent, "Foundit"),
        (GlassdoorAgent, "Glassdoor"),
        (IndeedAgent, "Indeed"),
    ]

    for agent_class, name in agent_classes:
        try:
            logger.info(f"  > Initializing {name} Agent...")
            driver = get_headless_driver(name)
            # FIX: All simple agents now accept driver= correctly (base_agent fixed)
            agent = agent_class(driver=driver)
            coordinator.register_agent(agent)
        except Exception as ex:
            logger.error(f"  ! Failed to start {name} Agent: {ex}")

    if not coordinator.agents:
        logger.error("No agents initialized. Exiting.")
        return

    logger.info(f"Fleet ready: {len(coordinator.agents)} agents active.")
    logger.info("Watching this window for all intelligence logs...")
    print("-" * 55)

    try:
        coordinator.start_mission(max_total_apps=100)
    except KeyboardInterrupt:
        coordinator.stop_mission()
    finally:
        logger.info("Fleet Mission Concluded.")


if __name__ == "__main__":
    # Pre-flight: Verify Ollama is running
    import requests as req
    try:
        req.get("http://localhost:11434/api/tags", timeout=5)
        logger.info("Ollama (Gemma 4) is online. ✓")
    except Exception:
        logger.error("CRITICAL: Ollama is not running. Start Ollama first.")
        sys.exit(1)

    launch_omni_agent_fleet()
