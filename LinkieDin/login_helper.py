import json
import os
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except ImportError:
    print("Please install selenium: pip install selenium")
    exit(1)

COOKIES_FILE = "linkedin_cookies.json"

opts = Options()
# Do NOT run headless, keep it fully visible for the user!
opts.add_argument("--disable-windows10-custom-titlebar")

driver = webdriver.Chrome(options=opts)

print("="*60)
print("LINKEDIN MANUAL LOGIN HELPER")
print("="*60)
print("A Chrome window just opened.")
print("Please log in to LinkedIn within that window.")
print("If you encounter a CAPTCHA or 'Let's do a quick security check', please solve it!")
print("-" * 60)

driver.get("https://www.linkedin.com/login")

input(">>>> PRESS ENTER HERE IN THE TERMINAL ONCE YOU ARE SEEING YOUR LINKEDIN FEED <<<<\n")

print("Extracting fresh cookies...")
cookies = driver.get_cookies()

li_at = next((c for c in cookies if c['name'] == 'li_at'), None)
if li_at:
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=4)
    print(f"✅ SUCCESS! Saved {len(cookies)} cookies to {COOKIES_FILE}")
    print("The fleet will now automatically pick this up.")
else:
    print("❌ FAILED. Could not find 'li_at' cookie. Are you sure you were fully logged in?")

driver.quit()
