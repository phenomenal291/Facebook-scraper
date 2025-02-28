import time
import random
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import json

def setup_logger():
    """
    Configures a logger for the scraper.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("scraper.log"),
            logging.StreamHandler()
        ]
    )

def get_webdriver(headless=False, proxy=None):
    """
    Configures and returns a Selenium WebDriver instance.
    """
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--mute-audio")
    options.add_argument("start-maximized")
    options.add_argument(f"user-agent={get_random_user_agent()}")

    if proxy:
        proxy_settings = Proxy()
        proxy_settings.proxy_type = ProxyType.MANUAL
        proxy_settings.http_proxy = proxy
        proxy_settings.ssl_proxy = proxy
        options.proxy = proxy_settings
    current_file = __file__
    CHROMEDRIVER_PATH =current_file.replace("Facebook_scraper.py", r"chromedriver-win64\chromedriver.exe")
    service = Service(CHROMEDRIVER_PATH)
    return webdriver.Chrome(service=service, options=options)


def get_random_user_agent():
    """
    Returns a random user-agent string.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0"
    ]
    return random.choice(user_agents)

def handle_captcha(driver):
    """
    Detects and handles CAPTCHA. Pauses for manual resolution if detected.
    """
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'CAPTCHA')]"))
        )
        input("Press Enter after solving the CAPTCHA manually.")
    except Exception:
        logging.info("No CAPTCHA detected.")

def load_cookies(driver, filename="facebook_cookies.json"):
    """
    Loads cookies from a file into the browser session.
    """
    try:
        with open(filename, "r") as file:
            cookies = json.load(file)
        for cookie in cookies:
            driver.add_cookie(cookie)
    except FileNotFoundError:
        logging.error(f"Cookie file {filename} not found.")
    except json.JSONDecodeError:
        logging.error(f"Cookie file {filename} is invalid. Please create it.")

def facebook_login_with_cookies(driver, cookies_file="facebook_cookies.json"):
    """
    Logs into Facebook using saved cookies. If cookies are invalid.
    """
    driver.get("https://www.facebook.com/")
    load_cookies(driver, cookies_file)
    driver.refresh()
    time.sleep(5)

    if "login" in driver.current_url:
        return False
    return True

def scrape_facebook_posts(driver, keyword, max_posts=50):
    """
    Searches for a keyword and scrapes posts.
    """
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='search' and contains(@aria-label, 'Tìm kiếm')]"))
        )
        search_box.send_keys(Keys.CONTROL + "a")
        search_box.send_keys(Keys.DELETE)
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.RETURN)

        time.sleep(5)
        handle_captcha(driver)
    except Exception as e:
        return []

    posts = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    timeout = time.time() + 120 
     
     # Create an ActionChains object
    actions = ActionChains(driver)

    while len(posts) < max_posts and scroll_attempts < 5:
        elements = driver.find_elements(By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z")

        for elem in elements:
            if len(posts) >= max_posts:
                break

            try:
                xem_them_button = elem.find_element(By.XPATH, ".//div[contains(text(), 'Xem thêm')]")
                driver.execute_script("arguments[0].click();", xem_them_button)
                time.sleep(1)
            except Exception as e:
                logging.debug(f"No 'Xem thêm' button found or unable to click: {e}")

            try:
                # Use a relative XPath to find the child element
                story_elem = elem.find_element(By.XPATH, ".//div[@data-ad-rendering-role='story_message']")
            except Exception as e:
                logging.debug(f"Could not extract text from the element: {e}")
                continue
            text = story_elem.text.strip()
            if text and text not in posts:
                logging.info("just scraped a post!")  
            else:
                continue

            # Hover over the <span> element and extract a link
            old_url = driver.current_url
            link = None
            try:
                span_elem = elem.find_element(By.CSS_SELECTOR, "span.html-span.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x1hl2dhg.x16tdsg8.x1vvkbs.x4k7w5x.x1h91t0o.x1h9r5lt.x1jfb8zj.xv2umb2.x1beo9mf.xaigb6o.x12ejxvf.x3igimt.xarpa2k.xedcshv.x1lytzrv.x1t2pt76.x7ja8zs.x1qrby5j")
                span_elem.click()
                driver.execute_script("arguments[0].click();", span_elem)
                # Wait until the URL changes or a specific element loads on the new page
                WebDriverWait(driver, 10).until(lambda d: d.current_url != old_url)
                link = driver.current_url
                # Now go back to the previous page
                driver.back()
                # Optionally, wait until the page returns to the previous state
                WebDriverWait(driver, 10).until(lambda d: d.current_url == old_url)
            except Exception as e:
                logging.debug(f"Could not hover or extract link from the span: {e}")

            posts.append({"text": text, "link": link, "keyword": keyword})

        # Scroll down and check for new content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2, 5))
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            scroll_attempts += 1
            logging.info(f"No new content loaded. Scroll attempts: {scroll_attempts}")
        else:
            scroll_attempts = 0

        if time.time() > timeout:
            logging.warning("Scrolling timed out.")
            break

        last_height = new_height

    logging.info(f"Scraped {len(posts)} posts.")
    return posts

def save_to_excel(data, filename="facebook_posts.xlsx"):
    """
    Saves data to a excel file.
    """
    # data.append("                     ")
    # data.append("#####   #   #   #### ")
    # data.append("#       ##  #   #   #")
    # data.append("#####   # # #   #   #")
    # data.append("#       #  ##   #   #")
    # data.append("#####   #   #   #### ")
    # data.append("                     ")

    import openpyxl
    df = pd.DataFrame(data)
    df.rename(columns={'text': 'Post Content', 'link': 'Link', 'keyword': 'Keyword'}, inplace=True)
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Posts", index=False)

if __name__ == "__main__":

    headless = True
    proxy = None
    max_posts = 20

    setup_logger()
    driver = get_webdriver(headless=headless, proxy=proxy)
    if not facebook_login_with_cookies(driver):
        logging.error("Login failed. Exiting.")
        driver.quit()
        exit()
    with open('keywords.txt', 'r', encoding='utf-8') as file:
        keywords = [line.strip() for line in file if line.strip()]
    all_posts=[]
    for keyword in keywords:
        posts = scrape_facebook_posts(driver, keyword, max_posts)
        if posts:
            all_posts.extend(posts)
        else:
            logging.info(f"No posts found for: {keyword}")
    if all_posts:
        save_to_excel(all_posts)
    else:
        save_to_excel([])
    # from time import sleep
    # sleep(5)
    
    driver.quit()
