import os
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from google_crawler.google_crawler import GoogleCrawler
from content_scraper.content_scraper import ContentScraper
from utils.logger import setup_logging
from utils.load_files import load_keywords, load_whitelist

def main():
    """Main function to run the crawler and scraper workflow"""
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Google search and content extraction workflow")
    
    time_start = datetime.now()
    try:
        # Step 1: Load keywords from file
        logger.info("Loading keywords from file...")
        keywords = load_keywords()
    
        if not keywords:
            logger.error("No valid keywords provided. Exiting.")
            return
        
        # Configure crawler parameters
        results_per_keyword = 100  # Target number of results per keyword
        max_pages = 4  # Maximum pages to check per keyword
        whitelist = load_whitelist()

        # Step 2: Initialize content scraper
        logger.info("Initializing content scraper...")
        content_scraper = ContentScraper(logger=logger, selenium_headless=True)
        
        # Step 3: Run Google crawler with immediate content extraction
        logger.info("Starting Google search crawler with immediate content extraction...")
        google_crawler = GoogleCrawler(logger=logger)
        search_results, content_results = google_crawler.run(
            keywords=keywords, 
            results_per_keyword=results_per_keyword,
            max_pages=max_pages,
            whitelist=whitelist,
            content_extractor=content_scraper,
            extractor_method='scrape'  # Method name to call on content_scraper
        )
        content_scraper.close()

        # Step 4: Log results summary
        logger.info("===== Workflow Summary =====")
        logger.info(f"Google search found {len(search_results)} total results")
        logger.info(f"Successfully extracted content from {len(content_results)} URLs")
        
        # Step 5: Save results to Excel
        if content_results:
            # Create output dir if needed
            if not os.path.exists('outputs'):
                os.makedirs('outputs')
                
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"outputs/search_results_{timestamp}.xlsx"
            
            # Save to Excel
            df = pd.DataFrame(content_results)

            # count results per keyword
            keyword_counts = df['keyword'].value_counts().to_dict()
            logger.info(f"Results per keyword: {keyword_counts}")

            df.to_excel(output_file, index=False)
            logger.info(f"Saved {len(content_results)} results to {output_file}")
        else:
            logger.warning("No content was extracted. Excel file not created.")
            
    except Exception as e:
        logger.error(f"Error in main workflow: {str(e)}")
        logger.exception("Exception details:")
    
    time_end = datetime.now()
    time_elapsed = time_end - time_start
    logger.info(f"Workflow completed in {time_elapsed}")

if __name__ == "__main__":
    main()