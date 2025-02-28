from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import json

service = Service("chromedriver.exe")
browser = webdriver.Chrome(service=service)

# Open Facebook login page
browser.get("https://facebook.com")

# Wait for you to login manually. Once logged in, press Enter in the console.
input("After logging in, press Enter to save cookies...")

# Capture cookies and write to file.
cookies = browser.get_cookies()
with open("facebook_cookies.json", "w", encoding="utf-8") as f:
    json.dump(cookies, f, indent=4)

browser.quit()