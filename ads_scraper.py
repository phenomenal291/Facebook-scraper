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
import json
import re
from pathlib import Path


class AdsScraperLogger:
    """
    Handles logging configuration for the Facebook scraper.
    """
    @staticmethod
    def setup():
        """
        Sets up logging to both console and file.
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("scraper.log", encoding = "utf-8"),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger("AdsScraper")
class BrowserManager:
    """
    Manages browser instance creation and configuration.
    """
    @staticmethod
    def get_random_user_agent():
        """
        Returns a random user-agent to avoid detection.
        """
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0"
        ]
        return random.choice(user_agents)
    
    @staticmethod
    def create_browser(headless=False, proxy=None):
        """
        Creates and configures a Chrome browser instance.
        Args:
            headless: If True, browser will run without a visible window
            proxy: Optional proxy server configuration
        Returns:
            A configured Chrome WebDriver instance
        """
        options = webdriver.ChromeOptions()
        
        # Configure browser options
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--mute-audio")
        options.add_argument("start-maximized")
        options.add_argument(f"user-agent={BrowserManager.get_random_user_agent()}")

        # Configure proxy if provided
        if proxy:
            proxy_settings = Proxy()
            proxy_settings.proxy_type = ProxyType.MANUAL
            proxy_settings.http_proxy = proxy
            proxy_settings.ssl_proxy = proxy
            options.proxy = proxy_settings
            
        # Set up ChromeDriver path
        current_file = __file__
        chromedriver_path = current_file.replace("ads_scraper.py", r"chromedriver.exe")
        service = Service(chromedriver_path)
        return webdriver.Chrome(service=service, options=options)
    
class AdsScraper:
    
    def __init__(self, headless=True, proxy=None):
        """
        Initialize the Facebook scraper.
        
        Args:
            headless: Whether to run the browser in headless mode
            proxy: Optional proxy server to use
            cookies_file: Path to the file containing Facebook cookies
        """
        self.logger = AdsScraperLogger.setup()
        self.driver = BrowserManager.create_browser(headless, proxy)
        self.logger.info("Ads scraper initialized")
    
    def scrape_posts(self, keyword, maxposts = 50):
        self.driver.get("https://www.facebook.com/ads/library/")
        
        
        ads_category = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, ".//span[contains(text(),'All ads') or contains(text(), 'Tất cả quảng cáo')]"))
            )
        self.driver.execute_script("arguments[0].click();", ads_category)
        time.sleep(random.uniform(2,4))
        search_box = self.driver.find_element(By.XPATH, ".//input[@type='search']")
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.RETURN)
    
        posts = []
        link = None
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        timeout = time.time() + maxposts*5
    
        try:
            elems = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'xh8yej3')]"))
            )
        except Exception as e:
            print("Error finding ads:", e)
        
        while ( len(posts) < maxposts and scroll_attempts < 5):
            ads = elems.find_elements(By.XPATH, "//div[contains(@class, '_7jyg _7jyh')]")
            for ad in ads:
                if ( len(posts) >= maxposts):
                    break
        
                text = ad.text
                
                if not text or text in [p["text"] for p in posts]:
                        continue
                    
                    
                link = ad.find_element(By.CLASS_NAME, "xt0psk2.x1hl2dhg.xt0b8zv.x8t9es0.x1fvot60.xxio538.xjnfcd9.xq9mrsl.x1yc453h.x1h4wwuj.x1fcty0u")
                link = link.get_attribute('href')
                
                imgs = ad.find_elements(By.TAG_NAME, "img")
                vids = ad.find_elements(By.TAG_NAME, "video")
                
                images = [ img.get_attribute("src") for img in imgs]
                images = images[1:]     ## remove the image of profile
                videos = [vid.get_attribute("src") for vid in vids]
                
                clean_text = self.remove_emojies(text)
                posts.append({"text": clean_text, "link": link, "image": images, "video": videos,"keyword": keyword})
                self.logger.info("Ads Scraped")
                
            # Scroll to load more content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 5))
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Check if we reached the end or timeout
            if new_height == last_height:
                scroll_attempts += 1
                ## logger.info(f"No new content loaded. Scroll attempt {scroll_attempts}/5")
            else:
                scroll_attempts = 0
                try:
                    elems = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'xh8yej3')]"))
                    )
                except Exception as e:
                    print("Error finding ads:", e)
                    break

            if time.time() > timeout:
                ## self.logger.warning("Scrolling timed out")
                break

            last_height = new_height
        self.logger.info(f"Scraped {len(posts)} posts for keyword '{keyword}'")
        return posts
    
    def close(self):
        if self.driver:
            self.driver.quit()
        self.logger.info("Browser closed")
        
    def remove_emojies(self,text):    
        emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & pictographs
        "\U0001F680-\U0001F6FF"  # Transport & map symbols
        "\U0001F700-\U0001F77F"  # Alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric symbols
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"  # Enclosed characters
        "]+", flags=re.UNICODE)
        return emoji_pattern.sub(r'', text)
        
    @staticmethod
    def save_to_excel(data, filename="ads_posts.xlsx"):
        """
        Saves scraped post data to an Excel file with plain text formatting.
        
        Args:
            data: List of post dictionaries
            filename: Output Excel file name
        """
        if not data:
            logging.info("No data to save to Excel.")
            return

        df = pd.DataFrame(data)
        df.rename(columns={'text': 'Post Content', 'link': 'Link', 'image' : 'Image', 'video': 'Video','keyword': 'Keyword'}, inplace=True)
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Posts", index=False)
            
        logging.info(f"Data saved to {filename}")
    
        

def main():
    headless = False  # Run without showing browser window if True
    proxy = None     # No proxy by default
    max_posts = 5   # Number of posts to scrape per keyword
    
    scraper = AdsScraper(headless=headless, proxy=proxy)
    
    try:
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
        AdsScraper.save_to_excel(all_posts)
        
    finally:
        # Always close the browser
        scraper.close()


if __name__ == "__main__":
    main()
