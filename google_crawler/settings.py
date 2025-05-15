import os
from importlib import import_module

# Basic Scrapy settings
BOT_NAME = 'google_crawler'
SPIDER_MODULES = ['google_crawler.spiders']
NEWSPIDER_MODULE = 'google_crawler.spiders'

# Scrapy behavior settings
ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS = 1
COOKIES_ENABLED = True
DOWNLOAD_TIMEOUT = 60
RETRY_TIMES = 1
RETRY_HTTP_CODES = [500, 502, 503, 504, 403, 408, 429]

# Output encoding
FEED_EXPORT_ENCODING = 'utf-8'

# Turn off headless mode to allow user to solve CAPTCHAs
SELENIUM_HEADLESS = True
SELENIUM_DRIVER_WAIT_TIME = 10

# Tell scrapy-selenium to use our factory function
SELENIUM_DRIVER_FACTORY = 'utils.selenium_utils.selenium_driver_factory'

# Enable the middleware
DOWNLOADER_MIDDLEWARES = {
    'google_crawler.middlewares.SeleniumMiddleware': 800,
    'scrapy_selenium.SeleniumMiddleware': None,  # Disable the original
     'scrapy.downloadermiddlewares.robotstxt.RobotsTxtMiddleware': None,
}

# Enable AutoThrottle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

LOG_LEVEL = 'INFO'