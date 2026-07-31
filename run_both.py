"""
Master Automation Runner
========================
Runs Santosh and Pavan's Naukri automation simultaneously.
Each runs in their own isolated folder — no role mixing possible.

Usage:
    python run_both.py
"""
import subprocess
import sys
import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── CONFIG ────────────────────────────────────────────────────────────────────
BASE   = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

PROFILES = {
    "SANTOSH": {
        "folder":  os.path.join(BASE, "NowCurry"),
        "resume":  "SANTOSH CHAVALA.pdf",
        "auto_login": False,      # uses saved cookies — no re-login needed
    },
    "PAVAN": {
        "folder":  os.path.join(BASE, "NowCurry_Pavan"),
        "resume":  "PAVAN_KALYAN.pdf",
        "auto_login": True,       # auto-fills credentials from config.json
    },
}

# ─── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE, "master_run.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("master")


def run(name, folder, script, label):
    """Run a script inside a profile folder, stream output with [NAME] prefix."""
    script_path = os.path.join(folder, script)
    if not os.path.exists(script_path):
        log.warning(f"[{name}] SKIP — {script} not found")
        return True

    log.info(f"[{name}] START  {label}")
    result = subprocess.run(
        [PYTHON, script_path],
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in (result.stdout + result.stderr).splitlines():
        log.info(f"[{name}] {line}")

    ok = result.returncode == 0
    log.info(f"[{name}] {'OK' if ok else 'FAILED'}  {label}")
    return ok


def run_pipeline(name, cfg):
    """Full pipeline for one person: login → resume → jobs → profile-active."""
    if name == "PAVAN":
        log.info(f"[{name}] Staggering start by 45 seconds to prevent rate limit 406 errors...")
        time.sleep(45)

    folder = cfg["folder"]
    log.info(f"\n{'='*60}")
    log.info(f"[{name}] Pipeline starting  →  {folder}")
    log.info(f"{'='*60}")

    # Step 1 — Login (only if auto_login is needed)
    if cfg["auto_login"]:
        ok = run(name, folder, "interactive_login.py", "Auto Login")
        if not ok:
            log.error(f"[{name}] Login failed — skipping rest of pipeline")
            return

    # Step 2 — Upload resume
    resume = os.path.join(folder, cfg["resume"])
    if os.path.exists(resume):
        run(name, folder, "naukri_resume_uploader.py", "Resume Upload")
    else:
        log.warning(f"[{name}] Resume not found: {resume} — skipping upload")

    # Step 3 — Job search & apply
    script_path = os.path.join(folder, "main.py")
    config_path = os.path.join(folder, "config.json")
    log.info(f"[{name}] START  Job Search & Apply")
    result = subprocess.run(
        [PYTHON, script_path, "--config", config_path],
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in (result.stdout + result.stderr).splitlines():
        log.info(f"[{name}] {line}")
    log.info(f"[{name}] {'OK' if result.returncode == 0 else 'FAILED'}  Job Search & Apply")

    log.info(f"[{name}] Pipeline complete")


def main():
    log.info("=" * 60)
    log.info("  NAUKRI MASTER AUTOMATION — SANTOSH + PAVAN")
    log.info("=" * 60)
    log.info("Running both profiles simultaneously...\n")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(run_pipeline, name, cfg): name
            for name, cfg in PROFILES.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
            except Exception as e:
                log.error(f"[{name}] Unhandled error: {e}")

    log.info("\n" + "=" * 60)
    log.info("  BOTH PIPELINES DONE")
    log.info("=" * 60)
    log.info("NOTE: keep_profile_active.py runs every 2 hours.")
    log.info("Run it separately in two terminals if you want it active:")
    log.info("  Terminal 1: cd NowCurry       && python keep_profile_active.py")
    log.info("  Terminal 2: cd NowCurry_Pavan && python keep_profile_active.py")


if __name__ == "__main__":
    main()
