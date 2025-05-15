import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from google_crawler.spiders.google_spider import GoogleSpider
from scrapy import signals
from scrapy.signalmanager import dispatcher

from utils.logger import silence_noisy_log

class GoogleCrawler:
    """
    Manages the Google search crawling process using Scrapy and returns links directly
    """
    
    def __init__(self, logger=None):
        """
        Initialize the Google crawler
        
        Args:
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.search_results = []  # Will store search results directly
        
        self._content_extractor = None
        self.content_results = []  # Store content extraction results if scraper is provided
            
    def run(self, keywords=None, results_per_keyword=20, max_pages=10,
            whitelist=None, content_extractor=None, extractor_method=None, 
            **extractor_kwargs):
        """
    Run the Google crawler and return search results directly
    
    Args:
        keywords (list): List of keywords to search for
        results_per_keyword (int): Target number of results per keyword
        max_pages (int): Maximum number of pages to crawl per keyword
        whitelist (list): Optional list of domains to skip
        content_extractor: Optional object that will extract content from search results
        extractor_method (str): Name of the method to call on the content_extractor
        **extractor_kwargs: Additional keyword arguments to pass to the extractor method
        
    Returns:
        tuple: (search_results, extracted_content) if content_extractor is provided,
              otherwise just search_results
    """
        self.logger.info("Initializing Google search crawler")
        self.search_results = []  # Reset results
        self.content_results = [] # Reset content results

        # Set up processor if provided
        self._content_extractor = None
        if content_extractor and extractor_method:
            if hasattr(content_extractor, extractor_method) and callable(getattr(content_extractor, extractor_method)):
                # Create a partial function that includes any additional kwargs
                self._content_extractor = {
                    'extractor': content_extractor,
                    'method': extractor_method,
                    'kwargs': extractor_kwargs
                }
            else:
                self.logger.warning(f"Content extractor {content_extractor} does not have callable method {extractor_method}")
        
        if not keywords:
            self.logger.warning("No keywords provided to GoogleCrawler")
            return ([], []) if self.content_scraper else []
            
        self.logger.info(f"Starting Google crawler with {len(keywords)} keywords")
        self.logger.info(f"Target: collect up to {results_per_keyword} results per keyword")
        self.logger.info(f"Maximum {max_pages} pages will be crawled per keyword")
        
        try:
            # Configure Scrapy crawler process
            settings = get_project_settings()
            process = CrawlerProcess(settings)
            silence_noisy_log()  # Silence Scrapy log output

            # Set up the signal to collect items
            dispatcher.connect(self._item_scraped, signals.item_scraped)
            
            # Add the Google spider to the process with all parameters
            process.crawl(GoogleSpider, 
                         keywords=keywords, 
                         results_per_keyword=results_per_keyword,
                         max_pages=max_pages,
                         whitelist=whitelist)
            
            # Run the crawler
            self.logger.info(f"Starting Google search crawling (with content extractor: {self._content_extractor is not None})...")
            process.start()
            
            # Process is complete at this point
            self.logger.info(f"Google search crawling finished with {len(self.search_results)} total results")
            
            # Return appropriate results
            if self._content_extractor:
                return (self.search_results, self.content_results)
            else:
                return self.search_results
        except Exception as e:
            self.logger.error(f"Error during Google crawling: {str(e)}")
            self.logger.exception("Exception details:")
            return ([], []) if self._content_extractor else []
    
    def _item_scraped(self, item, response, spider):
        """
        Callback function for scrapy signal when an item is scraped
        """
        search_result = dict(item)
        self.search_results.append(search_result)
        # Process with content scraper if available
        if self._content_extractor:
            try:
                # Get the extractor details
                extractor = self._content_extractor['extractor']
                method_name = self._content_extractor['method']
                extra_kwargs = self._content_extractor['kwargs']
                
                # Call the method dynamically
                method = getattr(extractor, method_name)

                # Call the extractor method with the search result and any additional kwargs
                content_data = method(search_result, **extra_kwargs)
                
                if content_data:
                    self.content_results.append(content_data)
                else:
                    self.logger.warning(f"Failed to extract content from: {search_result['link']}")
                    
            except Exception as e:
                self.logger.error(f"Error extracting content from {search_result['link']}: {str(e)}")