import os
import unicodedata
import re
import time
import random
import logging
import json
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from utils import get_default_chrome_user_data_dir


class FacebookScraperLogger:
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
                logging.FileHandler("scraper.log", encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger("FacebookScraper")


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
    def create_browser(headless=False, proxy=None, user_data_dir = None, profile_name=None):
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

        if profile_name: # Use specified profile
            if not user_data_dir:
                user_data_dir = get_default_chrome_user_data_dir()
            options.add_argument(f"user-data-dir={user_data_dir}")
            options.add_argument(f'--profile-directory={profile_name}')

        # Configure proxy if provided
        if proxy:
            proxy_settings = Proxy()
            proxy_settings.proxy_type = ProxyType.MANUAL
            proxy_settings.http_proxy = proxy
            proxy_settings.ssl_proxy = proxy
            options.proxy = proxy_settings
            
        # Set up ChromeDriver path
        current_file = __file__
        chromedriver_path = current_file.replace("Facebook_scraper.py", r"chromedriver.exe")
        service = Service(chromedriver_path)
        
        return webdriver.Chrome(service=service, options=options)


class FacebookScraper:
    """
    Main class for scraping posts from Facebook based on keywords.
    """
    def __init__(self, headless=True, proxy=None, cookies_file=None, user_data_dir=None, profile_name=None, white_list=None):
        """
        Initialize the Facebook scraper.
        
        Args:
            headless: Whether to run the browser in headless mode
            proxy: Optional proxy server to use
            cookies_file: Path to the file containing Facebook cookies
            white_list: Path to whitelist file containing URL substrings to skip
        """
        self.logger = FacebookScraperLogger.setup()
        self.driver = BrowserManager.create_browser(headless, proxy, user_data_dir, profile_name)
        self.cookies_file = cookies_file
        self.white_list = white_list
        self.logger.info("Facebook scraper initialized")

    def load_white_list(self):
        """
        Load list of URLs to skip from a white_list file.
        
        Returns:
            List of domain substrings to skip/ignore.
        """
        white_list = []
        try:
            with open(self.white_list, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line:
                        white_list.append(line)
            self.logger.info(f"Loaded {len(white_list)} URLs from white_list")
        except FileNotFoundError:
            self.logger.warning(f"white_list file {self.white_list} not found")
        return white_list
    
    def handle_captcha(self):
        """
        Detects and handles CAPTCHA challenges.
        Pauses execution for manual resolution if a CAPTCHA is detected.
        """
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'CAPTCHA')]"))
            )
            input("CAPTCHA detected! Please solve it manually and press Enter when done.")
        except Exception:
            self.logger.debug("No CAPTCHA detected")

    def load_cookies(self):
        """
        Loads Facebook cookies from the specified file.
        """
        try:
            with open(self.cookies_file, "r") as file:
                cookies = json.load(file)
            for cookie in cookies:
                self.driver.add_cookie(cookie)
            self.logger.info(f"Cookies loaded from {self.cookies_file}")
        except FileNotFoundError:
            self.logger.error(f"Cookie file {self.cookies_file} not found")
        except json.JSONDecodeError:
            self.logger.error(f"Cookie file {self.cookies_file} is invalid")

    def login(self):
        """
        Logs into Facebook using saved cookies.
        
        Returns:
            bool: Whether the login was successful
        """
        self.logger.info("Logging into Facebook...")
        self.driver.get("https://www.facebook.com/")
        if self.cookies_file:
            self.load_cookies()
        self.driver.refresh()
        time.sleep(5)
        
        # Check if we're still on the login page
        if "login" in self.driver.current_url:
            self.logger.error("Login failed, still on login page. Please checking cookies file/profile browser.")
            return False
            
        self.logger.info("Login successful")
        return True

    def scrape_posts(self, keyword, max_posts=50):
        """
        Searches for posts containing the specified keyword and scrapes them.
        
        Args:
            keyword: The search term to find posts
            max_posts: Maximum number of posts to collect
            
        Returns:
            List of dictionaries containing scraped post data.
        """
        self.logger.info(f"Searching for posts with keyword: {keyword}")
        
        # Search for the keyword
        try:
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='search' and contains(@aria-label, 'Tìm kiếm')]"))
            )
            search_box.send_keys(Keys.CONTROL + "a")
            search_box.send_keys(Keys.DELETE)
            search_box.send_keys(keyword)
            current_url = self.driver.current_url
            search_box.send_keys(Keys.RETURN)
            
            WebDriverWait(self.driver, 15).until(
                lambda driver: driver.current_url != current_url
            )
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z"))
            )
            self.handle_captcha()
        except Exception as e:
            self.logger.error(f"Search failed: {str(e)}")
            return []

        # Begin collecting posts
        posts = []
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        timeout = time.time() + max_posts * 5
        whitelist_entries = self.load_white_list() if self.white_list else []
        
        while len(posts) < max_posts and scroll_attempts < 5:
            # Find post elements
            elements = self.driver.find_elements(By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z")

            for elem in elements:
                if len(posts) >= max_posts:
                    break

                # Try to expand truncated posts
                try:
                    xem_them_button = elem.find_element(By.XPATH, ".//div[contains(text(), 'Xem thêm')]")
                    self.driver.execute_script("arguments[0].click();", xem_them_button)
                    wait = WebDriverWait(self.driver, 5)
                    wait.until(lambda d: len(elem.find_elements(By.XPATH, ".//div[contains(text(), 'Xem thêm')]")) == 0)
                except Exception:
                    pass  # "See more" button not found, continue

                # Extract post content
                try:
                    story_elem = elem.find_element(By.XPATH, ".//div[@data-ad-rendering-role='story_message']")
                    text = story_elem.text.strip()
                    if not text or text in [p["text"] for p in posts]:
                        continue
                    self.logger.info("Post found!")

                    # Extract images
                    img_elements = elem.find_elements(By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z a[role='link'] img")
                    images = [img.get_attribute("src") for img in img_elements if "emoji.php" not in img.get_attribute("src")]

                    # Extract videos
                    video_elements = elem.find_elements(By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z a[role='link'] video")
                    videos = [video.find_element(By.XPATH, "./ancestor::a").get_attribute("href") for video in video_elements]

                    # Try to extract post link and date
                    old_url = self.driver.current_url
                    link = None
                    post_date = None
                    try:
                        span_elem = elem.find_element(By.CSS_SELECTOR, "span.html-span.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x1hl2dhg.x16tdsg8.x1vvkbs.x4k7w5x.x1h91t0o.x1h9r5lt.x1jfb8zj.xv2umb2.x1beo9mf.xaigb6o.x12ejxvf.x3igimt.xarpa2k.xedcshv.x1lytzrv.x1t2pt76.x7ja8zs.x1qrby5j")
                        # Scroll to element
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", span_elem)
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(span_elem))
                        # Extract date
                        actions = ActionChains(self.driver)
                        actions.move_to_element(span_elem).perform()
                        date_tooltip = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.x11i5rnm.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x78zum5.xjpr12u.xr9ek0c.x3ieub6.x6s0dn4"))
                        )
                        WebDriverWait(self.driver, 5).until(lambda d: date_tooltip.text.strip() != "")
                        post_date = date_tooltip.text.strip()

                        # Extract link
                        span_elem.click()
                        WebDriverWait(self.driver, 15).until(lambda d: d.current_url != old_url)
                        WebDriverWait(self.driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
                        link = self.driver.current_url

                        # Close current post
                        self.driver.back()
                        WebDriverWait(self.driver, 10).until(lambda d: d.current_url == old_url)
                    except Exception as e:
                        self.logger.debug(f"Could not extract post link/date: {str(e)}")

                    # Check whitelist: if any entry appears in the link, skip this post
                    skip_post = False
                    if link:
                        for entry in whitelist_entries:
                            if entry in link:
                                self.logger.info(f"Skipping post from whitelisted source: {link}")
                                skip_post = True
                                break
                    if skip_post:
                        continue

                    posts.append({"text": text, "link": link, "date": post_date, "images": images, "videos": videos, "keyword": keyword})
                except Exception as e:
                    self.logger.debug(f"Could not extract post content: {str(e)}")

            # Scroll to load more content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            initial_count = len(self.driver.find_elements(By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z"))
            initial_height = self.driver.execute_script("return document.body.scrollHeight")
            wait = WebDriverWait(self.driver, 10)
            try:
                wait.until(lambda d: (d.execute_script("return document.body.scrollHeight") > initial_height or 
                                        len(d.find_elements(By.CSS_SELECTOR, "div.x1yztbdb.x1n2onr6.xh8yej3.x1ja2u2z")) > initial_count))
            except:
                time.sleep(1)
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            # Check if we reached the end or timeout
            if new_height == last_height:
                scroll_attempts += 1
                self.logger.info(f"No new content loaded. Scroll attempt {scroll_attempts}/5")
            else:
                scroll_attempts = 0

            if time.time() > timeout:
                self.logger.warning("Scrolling timed out")
                break

            last_height = new_height

        self.logger.info(f"Scraped {len(posts)} posts for keyword '{keyword}'")
        return posts

    @staticmethod
    def clean_text(text):
        """
        Remove or replace characters that cause Excel errors.
        Handles multiple styles of Unicode mathematical alphabetic symbols.
        """
        if not isinstance(text, str):
            return text
        
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

    @staticmethod
    def save_to_excel(data, filename="facebook_posts.xlsx"):
        """
        Saves scraped post data to an Excel file with plain text formatting.
        
        Args:
            data: List of post dictionaries
            filename: Output Excel file name
        """
        # Clean text before creating DataFrame
        cleaned_data = []
        for post in data:
            cleaned_post = {}
            for key, value in post.items():
                if key == 'text':
                    cleaned_post[key] = FacebookScraper.clean_text(value)
                else:
                    cleaned_post[key] = value
            cleaned_data.append(cleaned_post)

        # Convert to a DataFrame
        df = pd.DataFrame(cleaned_data).fillna('')

        # Group by 'text'
        grouped = df.groupby('text', as_index=False).agg({
            'text': 'first',
            'link': lambda links: next((ln for ln in links if ln), ''),  # first non-empty link
            'date': 'first',  # Keep first date
            'images': 'first',  # Keep first images list
            'videos': 'first',  # Keep first videos list
            'keyword': lambda kw: ', '.join(set(kw))  # Combine keywords
        })

        grouped.sort_values(by='keyword', inplace=True)
        
        # Reorder columns to put text and link first
        column_order = ['text', 'link', 'date', 'images', 'videos', 'keyword']
        grouped = grouped[column_order]

        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                grouped.to_excel(writer, sheet_name="Posts", index=False)
                worksheet = writer.sheets["Posts"]
                for row in worksheet.iter_rows():
                    for cell in row:
                        cell.number_format = '@'
        except Exception as e:
            logging.error(f"Failed to save data to Excel: {e}")
            return

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
    cookies_file = "facebook_cookies.json"  # Cookies file path
    white_list = "white_list.txt"
    user_data_dir = None  # Use default Chrome user data directory
    profile_name = None   # Use the specified Chrome profile
    max_posts = 20        # Number of posts to scrape per keyword
    
    # Initialize scraper
    scraper = FacebookScraper(
        headless=headless, 
        proxy=proxy, 
        cookies_file=cookies_file,
        user_data_dir=user_data_dir, 
        profile_name=profile_name,
        white_list=white_list
    )
    
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