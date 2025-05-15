import logging
import time
from importlib import import_module
from scrapy import signals
from scrapy.http import HtmlResponse
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class SeleniumMiddleware:
    """Scrapy middleware handling the requests using selenium"""

    def __init__(self, driver_factory, wait_time, headless):
        """Initialize the selenium webdriver"""
        self.logger = logging.getLogger(__name__)
        self.driver_factory = driver_factory
        self.headless = headless
        self.wait_time = wait_time
        self.driver = None
        self.captcha_timeout = 300  # 5 minutes to solve CAPTCHA

    @classmethod
    def from_crawler(cls, crawler):
        """Initialize the middleware with the crawler settings"""
        # Get driver factory path from settings
        factory_path = crawler.settings.get('SELENIUM_DRIVER_FACTORY')
        if not factory_path:
            raise ValueError('SELENIUM_DRIVER_FACTORY must be set')
        
        # Import the factory function
        module_path, factory_name = factory_path.rsplit('.', 1)
        module = import_module(module_path)
        driver_factory = getattr(module, factory_name)
        
        # Get wait time from settings
        wait_time = crawler.settings.get('SELENIUM_DRIVER_WAIT_TIME', 2)
        headless = crawler.settings.getbool('SELENIUM_HEADLESS', False)  # Default to visible browser
        
        # Create middleware instance
        middleware = cls(driver_factory, wait_time, headless)
        
        # Connect to the spider_closed signal
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        
        return middleware
    
    def init_driver(self):
        """Initialize the driver if it doesn't exist yet"""
        if self.driver is None:
            self.logger.info("Initializing Selenium WebDriver")
            self.driver = self.driver_factory(headless=self.headless)
    
    def detect_captcha(self):
        """Check if the current page contains a CAPTCHA"""
        captcha_indicators = [
            "//form[@action='/sorry']",  # Google's CAPTCHA/sorry page
            "//div[contains(text(), 'captcha')]",
            "//input[@id='captcha']",
            "//img[contains(@src, 'captcha')]",
            "//div[contains(@class, 'g-recaptcha')]",
            "//iframe[contains(@src, 'recaptcha')]",
            "//textarea[@id='g-recaptcha-response']"
        ]
        
        for indicator in captcha_indicators:
            try:
                elements = self.driver.find_elements(By.XPATH, indicator)
                if elements:
                    return True
            except:
                pass
        return False

    def handle_captcha(self):
        """Handle CAPTCHA by waiting for user to solve it manually"""
        self.logger.warning("CAPTCHA detected! Please solve it manually.")
        print("\n" + "="*60)
        print("CAPTCHA DETECTED! Please solve it in the browser window.")
        print("You have {} minutes to solve the CAPTCHA.".format(self.captcha_timeout // 60))
        print("The crawler will continue automatically once the CAPTCHA is solved.")
        print("="*60 + "\n")
        
        # Wait for the CAPTCHA to be solved (checking every 5 seconds)
        start_time = time.time()
        while time.time() - start_time < self.captcha_timeout:
            if not self.detect_captcha():
                print("\nCAPTCHA solved! Continuing crawl...\n")
                self.logger.info("CAPTCHA solved. Continuing crawl.")
                # Additional safety wait after CAPTCHA solution
                time.sleep(3)
                return True
            time.sleep(5)
            
        self.logger.error("CAPTCHA not solved within timeout period.")
        return False

    def process_request(self, request, spider):
        """Process a request using the selenium driver if applicable"""
        # Skip if not selenium request
        if not request.meta.get('selenium'):
            return None

        # Initialize driver if not already done
        self.init_driver()
        
        # Set default headers for driver if needed (user agent)
        if request.headers:
            for key, value in request.headers.items():
                key_str = key.decode('utf-8').lower()
                if key_str == 'user-agent':
                    # Handle various forms of header values
                    user_agent = None
                    if isinstance(value, list) and value:
                        user_agent = value[0].decode('utf-8') if isinstance(value[0], bytes) else str(value[0])
                    elif isinstance(value, bytes):
                        user_agent = value.decode('utf-8')
                    else:
                        user_agent = str(value)
                    
                    if user_agent:
                        self.driver.execute_cdp_cmd(
                            'Network.setUserAgentOverride',
                            {'userAgent': user_agent}
                        )

        # Open the URL in the browser
        self.driver.get(request.url)
        
        # Wait for the specified amount of time
        wait_time = request.meta.get('wait_time', self.wait_time)
            
        # Check for wait_until condition
        if request.meta.get('wait_until'):
            try:
                WebDriverWait(self.driver, wait_time).until(
                    request.meta['wait_until']
                )
            except TimeoutException:
                self.logger.warning(f"Timeout waiting for condition at URL: {request.url}")
        else:
            # If no condition is specified, just wait
            time.sleep(wait_time)
        
        # Check for CAPTCHA
        if self.detect_captcha():
            captcha_solved = self.handle_captcha()
            if not captcha_solved:
                self.logger.error(f"Failed to solve CAPTCHA for URL: {request.url}")
                # Return an empty response if CAPTCHA wasn't solved
                return HtmlResponse(
                    request.url,
                    body=b"<html><body><p>CAPTCHA timeout</p></body></html>",
                    encoding='utf-8',
                    request=request,
                    status=403
                )
        
        # Get page source and create response
        body = self.driver.page_source.encode('utf-8')
        current_url = self.driver.current_url
        
        # Create the response
        response = HtmlResponse(
            current_url,
            body=body,
            encoding='utf-8',
            request=request
        )
        
        return response

    def spider_closed(self):
        """Shutdown the driver when spider is closed"""
        if self.driver:
            self.logger.info("Closing Selenium WebDriver")
            self.driver.quit()