"""
Install/Uninstall LinkedIn Service to Windows Startup
======================================================
Run this script to add or remove the background service
from Windows Startup.
"""

import os
import sys
import winreg

SERVICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linkedin_service.pyw")
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "LinkedInProfileUpdater"

def get_pythonw_path():
    """Find pythonw.exe path."""
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return None

def install():
    pythonw = get_pythonw_path()
    if not pythonw:
        print("ERROR: pythonw.exe not found!")
        return False

    command = f'"{pythonw}" "{SERVICE_FILE}"'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        print(f"SUCCESS: LinkedIn Service added to Windows Startup!")
        print(f"  Command: {command}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to add to startup: {e}")
        return False

def uninstall():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, REG_NAME)
        winreg.CloseKey(key)
        print(f"SUCCESS: LinkedIn Service removed from Windows Startup!")
        return True
    except FileNotFoundError:
        print("Not found in startup.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to remove from startup: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python install_startup.py [install|uninstall]")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    else:
        print(f"Unknown action: {action}")
