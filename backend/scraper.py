import requests
from bs4 import BeautifulSoup
import re
import random
import time
from urllib.parse import urljoin, urlparse
from typing import Set, Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from time import time as get_time

# Compile patterns once
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
PHONE_PATTERN = re.compile(r'\+?[\d\s-]{10,}')
CONTACT_KEYWORDS = {'contact', 'kontakt', 'about', 'o-nas', 'reach', 'kontakt', 'kontakty', 'contacts', 'email', 'mail', 'phone', 'telefon'}

# List of user agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59'
]

@dataclass
class ContactInfo:
    """Data class to store contact information"""
    value: str
    locations: Set[str] = field(default_factory=set)

class WebsiteScraper:
    def __init__(self, timeout=15, max_retries=3, delay_between_requests=1):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_between_requests = delay_between_requests
        self._rotate_user_agent()
    
    def _rotate_user_agent(self):
        """Rotate the user agent to avoid detection"""
        self.session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })

    def get_page(self, url: str) -> Tuple[Optional[BeautifulSoup], Optional[str]]:
        """Fetch and parse a webpage with retry logic"""
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        for attempt in range(self.max_retries):
            try:
                # Rotate user agent on each attempt
                if attempt > 0:
                    self._rotate_user_agent()
                
                # Add a delay between requests to be more polite
                if attempt > 0:
                    time.sleep(self.delay_between_requests * (attempt + 1))
                
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                
                # Check if we got a valid HTML response
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' not in content_type:
                    print(f"Skipping non-HTML content at {url}: {content_type}")
                    return None, None
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove script and style elements
                for element in soup(['script', 'style']):
                    element.decompose()
                
                return soup, soup.get_text(separator=' ', strip=True)
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    print(f"Failed to retrieve {url} after {self.max_retries} attempts: {e}")
                    return None, None
                # Exponential backoff
                time.sleep(2 ** attempt)
        return None, None

    def get_domain_links(self, soup: BeautifulSoup, base_url: str, base_domain: str) -> Set[str]:
        """Extract domain-specific links"""
        if not soup:
            return set()
            
        links = set()
        for a_tag in soup.find_all('a', href=True):
            try:
                href = a_tag['href'].strip()
                # Skip empty links, anchors, javascript, and mailto links
                if not href or href.startswith(('#', 'javascript:', 'tel:', 'sms:')):
                    continue
                    
                # Handle mailto links separately to extract emails
                if href.startswith('mailto:'):
                    email = href[7:].split('?')[0].strip()
                    if EMAIL_PATTERN.match(email):
                        continue  # We'll handle this in the email extraction
                
                full_url = urljoin(base_url, href)
                parsed_url = urlparse(full_url)
                
                # Only include links from the same domain
                if parsed_url.netloc == base_domain:
                    # Normalize the URL
                    normalized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    if parsed_url.query:
                        normalized_url += f"?{parsed_url.query}"
                    links.add(normalized_url)
            except Exception as e:
                continue
        return links

    def extract_emails_from_soup(self, soup: BeautifulSoup, url: str) -> Set[str]:
        """Extract emails from HTML elements like mailto links"""
        emails = set()
        
        # Extract from mailto links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').strip()
            if href.startswith('mailto:'):
                email = href[7:].split('?')[0].strip()
                if EMAIL_PATTERN.match(email):
                    emails.add(email)
        
        # Extract from elements with data attributes that might contain emails
        for element in soup.find_all(attrs={"data-email": True}):
            email = element.get("data-email", "").strip()
            if EMAIL_PATTERN.match(email):
                emails.add(email)
        
        return emails

    def scrape_site(self, url: str, max_pages=10) -> Dict:
        """Scrape a single website for contact information"""
        start_time = get_time()
        
        # Normalize URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        parsed_url = urlparse(url)
        base_domain = parsed_url.netloc
        if not base_domain:
            return {
                'domain': '',
                'emails': [],
                'phones': [],
                'pages_scanned': [],
                'scan_time': '0.00 seconds',
                'error': f"Invalid URL: {url}"
            }
        
        visited = set()
        to_visit = {url}
        emails = {}  # {email: ContactInfo}
        phones = {}  # {phone: ContactInfo}

        pages_visited = 0
        while to_visit and pages_visited < max_pages:
            current_url = to_visit.pop()
            if current_url in visited:
                continue

            # Add a small delay between requests to be polite
            if pages_visited > 0:
                time.sleep(self.delay_between_requests)
                
            soup, content = self.get_page(current_url)
            if not content:
                continue

            visited.add(current_url)
            pages_visited += 1

            # Extract contact information from text content
            if content:
                for email in EMAIL_PATTERN.findall(content):
                    if email not in emails:
                        emails[email] = ContactInfo(email)
                    emails[email].locations.add(current_url)

                for phone in PHONE_PATTERN.findall(content):
                    if phone not in phones:
                        phones[phone] = ContactInfo(phone)
                    phones[phone].locations.add(current_url)
            
            # Extract emails from HTML elements
            if soup:
                for email in self.extract_emails_from_soup(soup, current_url):
                    if email not in emails:
                        emails[email] = ContactInfo(email)
                    emails[email].locations.add(current_url)

                # Get new links
                new_links = self.get_domain_links(soup, current_url, base_domain)
                
                # Prioritize contact pages
                priority_links = {link for link in new_links 
                                if any(keyword in link.lower() for keyword in CONTACT_KEYWORDS)}
                to_visit.update(priority_links - visited)
                
                # Add remaining links if we haven't reached the limit
                if len(to_visit) < max_pages:
                    to_visit.update((new_links - priority_links) - visited)

        duration = get_time() - start_time
        return {
            'domain': base_domain,
            'emails': [{'value': info.value, 'found_on': list(info.locations)} 
                      for info in emails.values()],
            'phones': [{'value': info.value, 'found_on': list(info.locations)} 
                      for info in phones.values()],
            'pages_scanned': list(visited),
            'scan_time': f"{duration:.2f} seconds"
        }

def scrape_websites(urls: List[str], max_pages_per_site=10, max_workers=3) -> Dict:
    """Scrape multiple websites concurrently"""
    # Validate and normalize URLs
    valid_urls = []
    for url in urls:
        if url:
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            valid_urls.append(url)
    
    if not valid_urls:
        return {}
    
    scraper = WebsiteScraper()
    results = {}

    # Limit max_workers to avoid overwhelming the system
    effective_max_workers = min(max_workers, len(valid_urls))
    
    with ThreadPoolExecutor(max_workers=effective_max_workers) as executor:
        future_to_url = {
            executor.submit(scraper.scrape_site, url, max_pages_per_site): url 
            for url in valid_urls
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                if data and data.get('domain'):
                    results[data['domain']] = data
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
                # Add error information to results
                domain = urlparse(url).netloc
                if domain:
                    results[domain] = {
                        'domain': domain,
                        'emails': [],
                        'phones': [],
                        'pages_scanned': [],
                        'scan_time': '0.00 seconds',
                        'error': str(e)
                    }

    return results

# Example usage
if __name__ == "__main__":
    websites = [
        "https://almar.krakow.pl/",
        "https://www.sek.krakow.pl/",
        "https://www.pkdrew.pl/"
    ]
    
    results = scrape_websites(websites)
    
    for domain, data in results.items():
        print(f"\n{'='*50}")
        print(f"Results for {domain} (scanned in {data['scan_time']}):")
        print(f"{'='*50}")
        
        if 'error' in data:
            print(f"\nError: {data['error']}")
            continue
        
        if data['emails']:
            print("\nEmails found:")
            for email_info in data['emails']:
                print(f"\nEmail: {email_info['value']}")
                print("Found on pages:")
                for page in email_info['found_on']:
                    print(f"- {page}")
        else:
            print("\nNo emails found.")
        
        if data['phones']:
            print("\nPhones found:")
            for phone_info in data['phones']:
                print(f"\nPhone: {phone_info['value']}")
                print("Found on pages:")
                for page in phone_info['found_on']:
                    print(f"- {page}")
        else:
            print("\nNo phone numbers found.")