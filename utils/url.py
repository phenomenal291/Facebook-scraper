from urllib.parse import urlparse, urljoin

def is_in_whitelist(url, whitelist):
    """
    Check if a URL in whitelist.
    Returns True if URL is in whitelist or is subdomain of whitelist entry
    """
    if not whitelist:
        return False
        
    try:
        # Parse the URL to extract the netloc (domain)
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Remove 'www.' prefix if exists
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check if domain is in whitelist or is a subdomain of a whitelisted domain
        for whitelisted_domain in whitelist:
            if domain == whitelisted_domain or domain.endswith('.' + whitelisted_domain):
                return True
                
        return False
    except Exception:
        return False  # Default to not skipping in case of error

def make_absolute_url(base_url, relative_url):
        """Convert a relative URL to an absolute URL"""
        if not relative_url:
            return ""
            
        # If it's already an absolute URL, return it as is
        if relative_url.startswith(('http://', 'https://')):
            return relative_url
        
        # Use urljoin which properly handles all cases of relative URLs
        absolute_url = urljoin(base_url, relative_url)
        return absolute_url

def get_base_domain(url):
        """Extract the base domain from a URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"