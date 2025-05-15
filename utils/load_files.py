from pathlib import Path
import logging

def load_keywords(keywords_file='keywords.txt'):
    """Load keywords from file"""
    logger = logging.getLogger(__name__)
    try:
        keywords_path = Path(keywords_file)
        if not keywords_path.exists():
            logger.error("Keywords file not found!")
            return []
        with open(keywords_path, 'r', encoding='utf-8') as f:
            keywords = [line.strip() for line in f if line.strip()]
        
        if not keywords:
            logger.error("No keywords found in file!")
            return []
            
        logger.info(f"Loaded {len(keywords)} keywords for searching: {keywords}")
        return keywords
        
    except Exception as e:
        logger.error(f"Error loading keywords: {str(e)}")
        return []  # Return an empty list instead of default keywords

def load_whitelist(whitelist_file='whitelist.txt'):
    """Load whitelist domains from file"""
    logger = logging.getLogger(__name__)
    try:
        whitelist_path = Path(whitelist_file)
        if not whitelist_path.exists():
            logger.warning(f"Whitelist file {whitelist_file} not found. No domains will be whitelisted.")
            return []
            
        with open(whitelist_path, 'r', encoding='utf-8') as f:
            domains = [line.strip() for line in f if line.strip()]
        
        if domains:
            logger.info(f"Loaded {len(domains)} domains to whitelist: {domains}")
        else:
            logger.info("Whitelist file is empty. No domains will be whitelisted.")
            
        return domains
        
    except Exception as e:
        logger.error(f"Error loading whitelist: {str(e)}")
        return []