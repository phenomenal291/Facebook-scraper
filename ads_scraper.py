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
from webdriver_manager.chrome import ChromeDriverManager
import json
from pathlib import Path
import re
import emoji
import unicodedata

from db_mapping import save_to_excel

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
        options.add_argument("--lang=vi")

        # Configure proxy if provided
        if proxy:
            proxy_settings = Proxy()
            proxy_settings.proxy_type = ProxyType.MANUAL
            proxy_settings.http_proxy = proxy
            proxy_settings.ssl_proxy = proxy
            options.proxy = proxy_settings
            
        # Set up ChromeDriver path
        current_file = __file__
        service = Service(service=(ChromeDriverManager().install()))
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
    
        url_checked = []
        link = None
        #new element
        post_date = None
        date_tooltip = None # date tooltip element
        poster_name = None  #name
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        timeout = time.time() + maxposts*5
    
        try:
            elems = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'xh8yej3')]"))
            )
        except Exception as e:
            print("Error finding ads:", e)
        
        while ( len(url_checked) < maxposts and scroll_attempts < 5):
            ads = elems.find_elements(By.XPATH, "//div[contains(@class, 'x1plvlek xryxfnj x1gzqxud x178xt8z xm81vs4 xso031l xy80clv xb9moi8 xfth1om x21b0me xmls85d xhk9q7s x1otrzb0 x1i1ezom x1o6z2jb x1kmqopl x13fuv20 xu3j5b3 x1q0q8m5 x26u7qi x9f619')]")
            for ad in ads:
                if ( len(url_checked) >= maxposts):
                    break
        
                try:
                    content = ad.find_element(By.XPATH, ".//div[contains(@class, '_7jyg _7jyh')]")
                    text = content.find_element(By.XPATH, ".//div[contains(@class, 'x6ikm8r x10wlt62')]").text
                except Exception as e:
                    self.logger.error(f"Error retrieving text from ad: {e}")
                    continue
                try:
                    link = ad.find_element(By.CLASS_NAME, "xt0psk2.x1hl2dhg.xt0b8zv.x8t9es0.x1fvot60.xxio538.xjnfcd9.xq9mrsl.x1yc453h.x1h4wwuj.x1fcty0u")
                    link = link.get_attribute('href')
                except Exception as e:
                    self.logger.error(f"Error retrieving link from ad: {e}")
                    continue
                #check if link is crawled
                if link in url_checked:
                        self.logger.info(f"Skip crawled post")
                        continue
                #add to list of crawled link
                url_checked.append(link)


                imgs = ad.find_elements(By.TAG_NAME, "img")
                vids = ad.find_elements(By.TAG_NAME, "video")
                
                images = [ img.get_attribute("src") for img in imgs]
                images = images[1:]     ## remove the image of profile
                videos = [vid.get_attribute("src") for vid in vids]
                
                #extract poster_name
                poster_name = ad.find_element(By.CSS_SELECTOR,"span.x8t9es0.x1fvot60.xxio538.x108nfp6.xq9mrsl.x1h4wwuj.x117nqv4.xeuugli").text
                #extract date
                date_text = ad.find_elements(By.CLASS_NAME, "x8t9es0.xw23nyj.xo1l8bm.x63nzvj.x108nfp6.xq9mrsl.x1h4wwuj.xeuugli")
                numbers = re.findall(r'\d+', date_text[1].text)
                post_date = '/'.join(numbers[:3])

                yield ({"name": poster_name,"text": text, "link": link, "date": post_date, "images": images, "videos": videos, "keyword": keyword})
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
        self.logger.info(f"Scraped {len(url_checked)} posts for keyword '{keyword}'")
    
    @staticmethod
    def clean_text(text):
        """
        Remove or replace characters that cause Excel errors.
        Handles multiple styles of Unicode mathematical alphabetic symbols.
        """
        if not isinstance(text, str):
            return text
        
        text = emoji.replace_emoji(text, "")
        # Dictionary of Unicode mathematical alphabetic symbols and their replacements
        replacements = {
            # Bold
            range(0x1D400, 0x1D433): lambda c: chr(ord(c) - 0x1D400 + ord('A')),  # Bold A-Z and a-z
            range(0x1D7CE, 0x1D7FF): lambda c: chr(ord(c) - 0x1D7CE + ord('0')),  # Bold numbers
            
            # Italic
            range(0x1D434, 0x1D467): lambda c: chr(ord(c) - 0x1D434 + ord('A')),  # Italic A-Z and a-z
            
            # Bold Italic
            range(0x1D468, 0x1D49B): lambda c: chr(ord(c) - 0x1D468 + ord('A')),  # Bold Italic A-Z and a-z
            
            # Script
            range(0x1D49C, 0x1D4CF): lambda c: chr(ord(c) - 0x1D49C + ord('A')),  # Script A-Z and a-z
            
            # Bold Script
            range(0x1D4D0, 0x1D503): lambda c: chr(ord(c) - 0x1D4D0 + ord('A')),  # Bold Script A-Z and a-z
            
            # Fraktur
            range(0x1D504, 0x1D537): lambda c: chr(ord(c) - 0x1D504 + ord('A')),  # Fraktur A-Z and a-z
            
            # Double-struck
            range(0x1D538, 0x1D56B): lambda c: chr(ord(c) - 0x1D538 + ord('A')),  # Double-struck A-Z and a-z
            
            # Bold Fraktur
            range(0x1D56C, 0x1D59F): lambda c: chr(ord(c) - 0x1D56C + ord('A')),  # Bold Fraktur A-Z and a-z
            
            # Sans-serif
            range(0x1D5A0, 0x1D5D3): lambda c: chr(ord(c) - 0x1D5A0 + ord('A')),  # Sans-serif A-Z and a-z
            
            # Sans-serif Bold
            range(0x1D5D4, 0x1D607): lambda c: chr(ord(c) - 0x1D5D4 + ord('A')),  # Sans-serif Bold A-Z and a-z
            range(0x1D7EC, 0x1D7F6): lambda c: chr(ord(c) - 0x1D7EC + ord('0')),  # Sans-serif Bold numbers
            
            # Sans-serif Italic
            range(0x1D608, 0x1D63B): lambda c: chr(ord(c) - 0x1D608 + ord('A')),  # Sans-serif Italic A-Z and a-z
        }
        
        
        # First normalize the text - this will separate characters from combining marks
        normalized = unicodedata.normalize('NFKD', text)
        result = ""
        for char in normalized:
            code = ord(char)
            
            # Skip control characters except tab, LF, CR
            if code < 32 and code not in (9, 10, 13):
                continue
            
            # Try replacing mathematical symbols
            replaced = False
            for char_range, replacement_func in replacements.items():
                if code in char_range:
                    result += replacement_func(char)
                    replaced = True
                    break
            
            # Keep the character if it wasn't replaced and is in BMP
            if not replaced:
                if code < 65536:  # Basic Multilingual Plane
                    result += char
        return result
    
    def close(self):
        if self.driver:
            self.driver.quit()
        self.logger.info("Browser closed")
   
    # @staticmethod
    # def save_to_excel(data, filename="ads_posts.xlsx"):
    #     """
    #     Saves scraped post data to an Excel file with plain text formatting.
        
    #     Args:
    #         data: List of post dictionaries
    #         filename: Output Excel file name
    #     """
    #     if not data:
    #         logging.info("No data to save to Excel.")
    #         return

    #     df = pd.DataFrame(data)
    #     df.rename(columns={'text': 'Post Content', 'link': 'Link', 'image' : 'Image', 'video': 'Video','keyword': 'Keyword'}, inplace=True)
        
    #     # Apply the cleaner row-wise
    #     for col in df.columns:
    #         df[col] = df[col].astype(str).apply(AdsScraper.clean_text)

    #     with pd.ExcelWriter(filename, engine='openpyxl') as writer:
    #         df.to_excel(writer, sheet_name="Posts", index=False)
            
    #     logging.info(f"Data saved to {filename}")
    
        

def main():
    headless = True
    proxy = None
    max_posts = 15
    
    scraper = AdsScraper(headless=headless, proxy=proxy)
    batch = []
    batch_size = 5

    # Using try/except here so the browser only closes on success/final step
    try:
        with open('keywords.txt', 'r', encoding='utf-8') as file:
            keywords = [line.strip() for line in file if line.strip()]
        
        for keyword in keywords:
            posts = scraper.scrape_posts(keyword, max_posts)
            for post in posts:
                batch.append(post)
                if(len(batch)>= batch_size):
                    save_to_excel(batch)
                    batch =[]
            #sau khi save vẫn dư ra 1 phần
            if batch:
                save_to_excel(batch)
                batch =[]
        
    except Exception as e:
        logging.error(f"Scraper error: {e}")
    finally:
        # Always close the browser 
        scraper.close()
        logging.info("Browser closed")

if __name__ == "__main__":
    main()
