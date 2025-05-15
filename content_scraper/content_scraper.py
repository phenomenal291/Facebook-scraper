import os
import re
import logging
import random
import time
import trafilatura

from copy import deepcopy
from trafilatura.settings import use_config

from utils.user_agents import get_user_agent_list
from utils.logger import silence_trafilatura_log
from utils.url import make_absolute_url, get_base_domain

class ContentScraper:
    """
    Content scraper that uses Trafilatura library to scrape content from a URL. 
    """
    
    def __init__(self, logger=None, selenium_headless=True):
        """Initialize the content scraper"""
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Load custom Trafilatura configuration
        config_path = os.path.join(os.path.dirname(__file__), 'setting.cfg')
        self.custom_config = use_config(config_path)
        self.logger.debug(f"Loaded Trafilatura config: {self.custom_config}")

        silence_trafilatura_log()
        self.driver = None # Selenium driver instance
        self.selenium_headless = selenium_headless # Use headless mode for Selenium
    
    def scrape(self, search_result):
        """
        Scrape content from a specific URL using Trafilatura's bare_extraction.
        
        Args:
            url (str): The URL to scrape
            keyword (str): The keyword that found this URL
            title (str): The title from search result (fallback)
            description (str): The description from search result (fallback)
            
        Returns:
            dict: Scraped content with standardized fields
        """
        url = search_result['link']
        keyword = search_result['keyword']
        title = search_result['title']
        description = search_result.get('description', '')
        
        self.logger.info(f"Scraping content from: {url}")
        
        try:  
            # Use trafilatura's built-in fetch function
            downloaded = trafilatura.fetch_url(
                url,
                config=self.custom_config,
            )
            
            if downloaded is None:
                self.logger.warning(f"Failed to download content from {url} with Trafilatura, trying Selenium")
                return self._try_selenium_scrape(url, keyword, title, description)
            
            # Extract rich content using bare_extraction
            extracted = trafilatura.bare_extraction(
                downloaded, 
                include_images=True, 
                with_metadata=True,
                config=self.custom_config
            )
            
            if not extracted:
                self.logger.warning(f"Trafilatura couldn't extract content from downloaded {url}, trying Selenium")
                return self._try_selenium_scrape(url, keyword, title, description)
            
            # Process extracted content
            return self._process_extracted_content(extracted, url, keyword, title, description)
            
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {str(e)}")
            return self._create_fallback_result(url, keyword, title, description, 
                                              f"Error extracting content")
    
    def _try_selenium_scrape(self, url, keyword, title, description):
        """Use Selenium as fallback for downloading and extracting content"""
        self.logger.info(f"Attempting to scrape {url} using Selenium")
        
        try:
            # Initialize Selenium driver if not already done
            if self.driver is None:
                from utils.selenium_utils import selenium_driver_factory
                self.driver = selenium_driver_factory(headless=self.selenium_headless)
                # Set page load timeout
                self.driver.set_page_load_timeout(30)
            
            # Navigate to URL with proper error handling
            try:
                from selenium.common.exceptions import TimeoutException, WebDriverException
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By
                
                self.driver.get(url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                self.logger.warning(f"Selenium: Timeout while loading page: {url}")
                return self._create_fallback_result(url, keyword, title, description, 
                                            f"Failed to download content")
            except WebDriverException as e:
                error_message = str(e).split('\n')[0].strip()
                self.logger.error(f"Selenium: Connection error for {url}: {str(e)}")
                return self._create_fallback_result(url, keyword, title, description, 
                                            f"Failed to download content")
            
            # Add a small delay to ensure dynamic content loads
            time.sleep(2)
            
            # Get the page source
            page_source = self.driver.page_source
            
            # Use Trafilatura to extract content from the page source
            extracted = trafilatura.bare_extraction(
                page_source,
                include_images=True,
                with_metadata=True,
                config=self.custom_config
            )
            
            if not extracted:
                self.logger.warning(f"Trafilatura (with Selenium) couldn't extract content from downloaded {url}")
                return self._create_fallback_result(url, keyword, title, description, 
                                                  "No content could be extracted")
            
            # Process extracted content
            return self._process_extracted_content(extracted, url, keyword, title, description)
            
        except Exception as e:
            self.logger.error(f"Error scraping (with Selenium) {url}: {str(e)}")
            return self._create_fallback_result(url, keyword, title, description, 
                                              f"Error extracting content")
        finally:
            # We don't close the driver here as we might reuse it for other scrapes
            pass
    
    def _process_extracted_content(self, extracted, url, keyword, search_title, search_description):
        """Process the extracted content and return standardized dict"""
        try:
            # Get content text - this is the main article content
            content = extracted.text if extracted.text else ""
            
            # Get title from metadata, use search result title as fallback
            page_title = extracted.title if extracted.title else search_title
            
            # Get description from metadata, use search result description as fallback
            page_description = extracted.description if extracted.description else search_description
            
            # Get date if available
            page_date = extracted.date if extracted.date else ""
            
            # Get main image if available
            main_image = extracted.image if extracted.image else ""
            # Convert main image to absolute URL if needed
            if main_image:
                main_image = make_absolute_url(url, main_image)

            # Get author if available
            author = extracted.author if extracted.author else ""
            
            # Get hostname/site data
            hostname = extracted.hostname if extracted.hostname else ""
            sitename = extracted.sitename if extracted.sitename else ""

            # Extract images from content
            content_cleaned, images = self._extract_images_from_content(content, url)
            
            self.logger.info(f"Successfully extracted content from {url}")
            
            # Return standardized format
            return {
                'title': page_title,
                'url': url,
                'description': page_description,
                'content': content_cleaned,
                'date': page_date,
                'main_image': main_image,
                'images': images,
                'author': author,
                'site': sitename or hostname,
                'keyword': keyword
            }
            
        except Exception as e:
            self.logger.error(f"Error processing extracted content: {str(e)}")
            return self._create_fallback_result(url, keyword, search_title, search_description,
                                              f"Error processing content")
    
    def _extract_images_from_content(self, content, base_url):
        """
        Extract images from content and replace with placeholders
        
        Args:
            content (str): Content text with possible image references
            base_url (str): The base URL of the page for resolving relative URLs
            
        Returns:
            tuple: (content_with_placeholders, list_of_image_urls)
        """
        if not content:
            return "", []
            
        images = []
        base_domain = get_base_domain(base_url)
        
        # Process Markdown images with both absolute and relative URLs
        # Format: ![alt text](image_path)
        markdown_pattern = r'!\[(.*?)\]\(([^)]+)\)'
        
        def replace_markdown_image(match):
            img_path = match.group(2)
            # Convert relative URL to absolute URL if needed
            img_url = make_absolute_url(base_url, img_path)
            
            if img_url not in images:
                images.append(img_url)
            img_index = images.index(img_url) + 1
            return f"[IMAGE-{img_index}]"
        
        # Replace markdown images with placeholders
        content_with_placeholders = re.sub(markdown_pattern, replace_markdown_image, content)
        
        # Look for any remaining absolute URLs that might be images
        url_pattern = r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)[^\s]*'
        
        def replace_url_with_placeholder(match):
            img_url = match.group(0)
            if img_url not in images:
                images.append(img_url)
            img_index = images.index(img_url) + 1
            return f"[IMAGE-{img_index}]"
        
        # Replace absolute image URLs with placeholders
        content_with_placeholders = re.sub(url_pattern, replace_url_with_placeholder, content_with_placeholders)
        
        return content_with_placeholders, images
    
    def _create_fallback_result(self, url, keyword, title, description, error_message):
        """Create a fallback result with error message"""
        return {
            'title': title,
            'url': url,
            'description': description,
            'content': error_message,
            'date': "",
            'main_image': "",
            'images': [],
            'author': "",
            'site': "",
            'keyword': keyword
        }
    
    def close(self):
        """Close selenium driver if it exists"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except Exception as e:
                self.logger.error(f"Error closing Selenium driver: {str(e)}")
