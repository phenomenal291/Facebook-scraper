from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def selenium_driver_factory(headless=False):
    """Create and return a Chrome WebDriver instance compatible with Selenium 4.x"""
    # Silence Selenium WebDriver logging
    import logging
    selenium_logger = logging.getLogger('selenium')
    selenium_logger.setLevel(logging.INFO)
    
    # Also silence related libraries
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.WARNING)
    
    options = webdriver.ChromeOptions()
    
    if headless:
        options.add_argument('--headless')
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Use Chrome driver manager to handle driver installation
    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    
    # Create the WebDriver with service and options
    driver = webdriver.Chrome(service=service, options=options)
    
    # Modify navigator.webdriver property to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver