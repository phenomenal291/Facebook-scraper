import scrapy
import logging
import urllib.parse
from urllib.parse import unquote

from utils.user_agents import get_lynx_useragent
from utils.url import is_in_whitelist

class GoogleSpider(scrapy.Spider):
    name = "GoogleSpider" 
    
    def __init__(self, keywords=None, results_per_keyword=20, max_pages=10, whitelist=None, *args, **kwargs):
        """
        Initialize spider with keywords provided externally
        
        Args:
            keywords (list): List of keywords to search for
            results_per_keyword (int): Number of results to fetch per keyword
            max_pages (int): Maximum number of pages to crawl per keyword
            whitelist (list): List of domains to skip (whitelist)
        """
        super(GoogleSpider, self).__init__(*args, **kwargs)
        self.keywords = keywords or []
        self.results_per_keyword = int(results_per_keyword)  # Ensure it's an integer
        self.max_pages = int(max_pages)  # Ensure it's an integer
        self.whitelist = whitelist or []

        self.logger.info(f"Spider initialized with {len(self.keywords)} keywords")
        self.logger.info(f"Target: {self.results_per_keyword} results per keyword, max {self.max_pages} pages per keyword")
        if self.whitelist:
            self.logger.info(f"Whitelist enabled with {len(self.whitelist)} domains to skip")

        # Dictionary to track count of results per keyword
        self.results_count = {keyword: 0 for keyword in self.keywords}
        
        # Track already visited keywords to avoid duplicates
        self.visited_urls = set()

        self.cookies = {
            'CONSENT': 'PENDING+987',  # Bypasses the consent page
            'SOCS': 'CAESHAgBEhIaAB',
        }
    
    def get_random_user_agent(self):
        """Get a random user agent string"""
        return get_lynx_useragent()
    
    def start_requests(self):
        """Generate initial search requests for each keyword"""
        self.logger.info(f"Starting requests for keywords: {self.keywords}")
        
        # Let Scrapy handle throttling and concurrency through its AutoThrottle extension
        for keyword in self.keywords:
            # Request as many results as needed on first page
            encoded_keyword = urllib.parse.quote(keyword)
            # Add num parameter to try to get more results on first page
            url = f"https://www.google.com/search?q={encoded_keyword}&num={self.results_per_keyword}&hl=vi&gl=vn&pws=0"
            
            # Use random user agent for each request
            user_agent = self.get_random_user_agent()
            
            self.logger.info(f"Starting search for: '{keyword}'")
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    "keyword": keyword,
                    "page": 0,
                    "selenium": False,  # Default to regular requests
                    "dont_merge_cookies": False,
                    "wait_time": 3,  # Wait 3 seconds for the page to load if use selenium
                },
                headers={"User-Agent": user_agent, "Accept": "*/*"},
                cookies=self.cookies,  # Add cookies to bypass consent page
                errback=self.errback_request  # Handle errors
            )

    def errback_request(self, failure):
        """
        Handle request failures and retry with Selenium
        This will be called after Scrapy's built-in retry mechanism has been exhausted
        """
        request = failure.request
        keyword = request.meta.get('keyword', 'unknown')
        current_page = request.meta.get('page', 'unknown')
        
        # Only retry with Selenium if not already using it
        if not request.meta.get("selenium", False):
            self.logger.warning(f"Request failed for '{keyword}' on page {current_page+1} after retries, switching to Selenium")
            
            # Create a new request using Selenium
            yield request.replace(
                meta={**request.meta, "selenium": True}
            )
        else:
            self.logger.error(f"Selenium request for '{keyword}' on page {current_page+1} also failed. Giving up.")

    def parse(self, response):
        keyword = response.meta["keyword"]
        current_page = response.meta["page"]
                
        self.logger.info(f"Processing page {current_page+1} for keyword: '{keyword}'")

        result_blocks = response.css("div.ezO2md")
        
        self.logger.info(f"Found {len(result_blocks)} raw results on page {current_page+1} for '{keyword}'")
        
        # Process search results
        results_on_page = 0
        
        for result in result_blocks:
            # Extract link - find <a> tag inside the result block
            link_raw = result.css("a::attr(href)").get()
            
            # Extract title - find <span class="CVA68e"> inside the <a> tag
            title = result.css("a span.CVA68e::text").get()
            
            # Extract description - find <span class="FrIlee"> 
            description_parts = result.css("span.FrIlee *::text").getall()
            description = ' '.join([part.strip() for part in description_parts]).strip() if description_parts else ""
            
            # Process link if it exists
            if link_raw and title:
                # Clean and decode the link URL
                link = unquote(link_raw.split("&")[0].replace("/url?q=", ""))
                
                # Check if it's a valid link, not already visited, and not in whitelist
                if (link.startswith('http') and 'google.com/search' not in link 
                    and link not in self.visited_urls
                    and not is_in_whitelist(link, self.whitelist)):
                    # Mark as visited
                    self.visited_urls.add(link)
                    
                    # Create and yield the result item
                    item = {
                        'keyword': keyword,
                        'title': title.strip(),
                        'link': link,
                        'description': description.strip() if description else ""
                    }
                    results_on_page += 1
                    self.results_count[keyword] += 1
                    yield item
        
        self.logger.info(f"Extracted {results_on_page} valid results from page {current_page+1} for '{keyword}'")
        self.logger.info(f"Total results for '{keyword}': {self.results_count[keyword]}/{self.results_per_keyword}")
        
        # Check if we need to fetch the next page for this keyword
        should_continue = (
            self.results_count[keyword] < self.results_per_keyword and  # Haven't found enough results
            current_page < self.max_pages - 1 and  # Haven't visited too many pages
            len(result_blocks) > 0  # Current page had results
        )
        
        if should_continue:
            # Look for the "Next" button link
            next_page_link = response.css("a.frGj1b::attr(href)").get()
            
            if next_page_link:
                next_url = f"https://www.google.com{next_page_link}"
                
                self.logger.info(f"Moving to next page for '{keyword}' to get more results")
                
                # Use random user agent for each request
                user_agent = self.get_random_user_agent()
                                
                # Let Scrapy's AutoThrottle handle the timing
                yield scrapy.Request(
                    url=next_url,
                    callback=self.parse,
                    meta={
                        "keyword": keyword,
                        "page": current_page + 1,  # Increment page counter
                        "selenium": False,
                        "dont_merge_cookies": False,
                        "wait_time": 3
                    },
                    headers={"User-Agent": user_agent, "Accept": "*/*"},
                    cookies=self.cookies,  # Add cookies to bypass consent page
                    errback=self.errback_request  # Handle errors
                )
            else:
                self.logger.warning(f"⚠ No 'Next' button found for '{keyword}' after {self.results_count[keyword]} results")
        else:
            if self.results_count[keyword] >= self.results_per_keyword:
                self.logger.info(f"✓ Reached target of {self.results_per_keyword} results for '{keyword}'")
            elif current_page >= self.max_pages - 1:
                self.logger.warning(f"⚠ Reached max page limit ({self.max_pages} pages) for '{keyword}' with only {self.results_count[keyword]} results")
            elif not result_blocks:
                self.logger.warning(f"⚠ No more results found for '{keyword}' after {self.results_count[keyword]} results")