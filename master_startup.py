"""
NowCurry Fleet Startup Manager
==============================
Installs/Uninstalls ALL automation services (Naukri, LinkedIn, Foundit, Glassdoor, Indeed)
to Windows Startup in one go.
"""

import os
import sys
import winreg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Map of (Registry Name, Service File Path)
PORTALS = {
    "NaukriProfilePulse": "NowCurry/naukri_service.pyw",
    "LinkedInProfilePulse": "LinkieDin/linkedin_service.pyw",
    "FounditProfilePulse": "Foundit/foundit_service.pyw",
    "GlassdoorProfilePulse": "GallasuDooru/glassdoor_service.pyw",
    "IndeedProfilePulse": "InDeed/indeed_service.pyw"
}

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_pythonw_path():
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    return pythonw if os.path.exists(pythonw) else None

def install():
    pythonw = get_pythonw_path()
    if not pythonw:
        print("ERROR: pythonw.exe not found!")
        return

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        for name, relative_path in PORTALS.items():
            abs_path = os.path.join(BASE_DIR, relative_path)
            if os.path.exists(abs_path):
                command = f'"{pythonw}" "{abs_path}"'
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
                print(f"✓ Installed: {name} ({relative_path})")
            else:
                print(f"⚠ Skipped: {relative_path} (File not found)")
        winreg.CloseKey(key)
        print("\nSUCCESS: All available services added to Windows Startup!")
    except Exception as e:
        print(f"ERROR: {e}")

def uninstall():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        for name in PORTALS.keys():
            try:
                winreg.DeleteValue(key, name)
                print(f"✗ Removed: {name}")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        print("\nSUCCESS: All services removed from Windows Startup!")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python master_startup.py [install|uninstall]")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    else:
        print(f"Unknown action: {action}")
