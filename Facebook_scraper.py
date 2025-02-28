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
                scroll_attempts = 0
                
            if time.time() > timeout:
                self.logger.warning("Scrolling timed out")
                break

            last_height = new_height

        self.logger.info(f"Scraped {len(posts)} posts for keyword '{keyword}'")
        return posts

    @staticmethod
    def save_to_excel(data, filename="facebook_posts.xlsx"):
        """
        Saves scraped post data to an Excel file with plain text formatting.
        
        Args:
            data: List of post dictionaries
            filename: Output Excel file name
        """
        df = pd.DataFrame(data)
        df.rename(columns={'text': 'Post Content', 'link': 'Link', 'keyword': 'Keyword'}, inplace=True)
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Posts", index=False)
            
        logging.info(f"Data saved to {filename}")

    def close(self):
        """
        Closes the browser and cleans up resources.
        """
        if self.driver:
            self.driver.quit()
        self.logger.info("Browser closed")


def main():
    """
    Main function that runs the Facebook scraper.
    """
    # Configuration
    headless = True  # Run without showing browser window if True
    proxy = None     # No proxy by default
    max_posts = 20   # Number of posts to scrape per keyword
    
    # Initialize scraper
    scraper = FacebookScraper(headless=headless, proxy=proxy)
    
    try:
        # Login to Facebook
        if not scraper.login():
            logging.error("Login failed. Exiting.")
            return
            
        # Load keywords from file
        with open('keywords.txt', 'r', encoding='utf-8') as file:
            keywords = [line.strip() for line in file if line.strip()]
            
        # Scrape posts for each keyword
        all_posts = []
        for keyword in keywords:
            posts = scraper.scrape_posts(keyword, max_posts)
            if posts:
                all_posts.extend(posts)
            else:
                logging.info(f"No posts found for keyword: {keyword}")
                
        # Save results to Excel
        FacebookScraper.save_to_excel(all_posts)
        
    finally:
        # Always close the browser
        scraper.close()


if __name__ == "__main__":
    main()