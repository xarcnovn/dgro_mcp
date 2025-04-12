import os
import json
import sqlite3
import asyncio
import re
import httpx
import requests
import time
import random
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from time import time as get_time
from typing import Dict, List, Optional, Any, Set, Tuple
from mcp.server.fastmcp import FastMCP, Context, Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants for website scraper
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
PHONE_PATTERN = re.compile(r'\+?[\d\s-]{10,}')
CONTACT_KEYWORDS = {'contact', 'kontakt', 'about', 'o-nas', 'reach', 'kontakt', 'kontakty', 'contacts', 'email', 'mail', 'phone', 'telefon'}

# List of user agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
]

PROMPT_TEMPLATE = """
You are a multi-agent system designed to help users find and negotiate the best offers for products or services. The process involves three specialized agents working together:

1. Consultant (First Point of Contact)
	•	Acts as a friendly and professional advisor who gathers details from the user.
	•	Dynamically asks relevant questions to deeply understand the user’s needs (e.g., budget, preferences, constraints).
	•	Must extract all necessary information in a maximum of five messages before passing the request to the Researcher.
    Tools you use:
    - precise_user_needs
    - update_case_info
    - get_case_info

Output:
	•	User’s Task: A clear, structured summary of what the user wants, including all key details.
	•	Google Search Query: A precise, 2-12 word phrase for finding vendors offering the desired service/product.

2. Researcher (Market Analyst & Vendor Finder)
	•	Uses Google Custom Search API to locate the best vendors/products matching the user’s needs.
	•	Verifies vendor credibility and compiles a list of relevant businesses with contact details for negotiations.
    Tools you use:
    - search_google
    - format_search_results
    - validate_and_save_vendors

Output:
	•	Curated Vendor List: Solid businesses that offer the required service/product with contact information.

3. Negotiator (Expert Deal-Maker) - don't run this step at the moment, it's not implemented yet
	•	Initiates contact with vendors, outlining the user’s request in a professional yet concise manner.
	•	Engages in tactical negotiations, applying principles from Never Split the Difference to get the best offer.
	•	Runs multiple negotiations in parallel, leveraging competing offers to secure better deals.
	•	Keeps the user informed, seeks approvals when necessary, and ultimately presents the best final offers.

Final Goal:
The system continuously refines the negotiation process until the user receives the best possible deal and makes a decision.
"""

# Initialize FastMCP server
mcp = FastMCP("price-comparison-assistant")

# SQLite database setup
DB_FILE = "price_comparison.db"

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create case_parameters table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS case_parameters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT,
        location TEXT,
        budget REAL,
        timeline TEXT,
        other_parameters TEXT
    )
    ''')
    
    # Create search table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id INTEGER,
        search_goal TEXT,
        search_query TEXT,
        search_results TEXT,
        FOREIGN KEY (id) REFERENCES case_parameters (id)
    )
    ''')
    
    # Create relevant_results table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS relevant_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_id INTEGER,
        websites TEXT,
        emails TEXT,
        reason TEXT,
        FOREIGN KEY (search_id) REFERENCES searches (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Initialize DB when the server starts
init_db()


# Helper functions for database operations
@mcp.tool()
def create_new_case(subject: str, location: str, budget: float, timeline: str, others: Optional[dict] = None) -> dict:
    """
    Create a new case for price comparison research. Use it only after a user has provided all the necessary information.
    
    Args:
        subject: What product or service the user is looking for
        location: Geographic location for the search
        budget: Budget constraint for the purchase
        timeline: When the user needs the product/service
        others: Other relevant parameters as a JSON object
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Insert the case parameters
        cursor.execute("""
        INSERT INTO case_parameters 
        (subject, location, budget, timeline, other_parameters)
        VALUES (?, ?, ?, ?, ?)
        """, (
            subject,
            location,
            budget,
            timeline,
            json.dumps(others or {})
        ))
        
        case_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "case_id": case_id,
            "message": f"New case created with ID: {case_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to create case: {str(e)}"
        }

def update_case_parameters(case_id: int, parameters: Dict[str, Any]) -> bool:
    """Update case parameters."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
    UPDATE case_parameters 
    SET subject = ?, location = ?, budget = ?, timeline = ?, other_parameters = ?
    WHERE id = ?
    """, (
        parameters.get('subject', ''),
        parameters.get('location', ''),
        parameters.get('budget', 0.0),
        parameters.get('timeline', ''),
        json.dumps(parameters.get('others', {})),
        case_id
    ))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_case_parameters(case_id: int) -> Dict[str, Any]:
    """Get case parameters."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT subject, location, budget, timeline, other_parameters
    FROM case_parameters
    WHERE id = ?
    """, (case_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return {}
    
    return {
        'subject': result[0],
        'location': result[1],
        'budget': result[2],
        'timeline': result[3],
        'others': json.loads(result[4] or '{}')
    }

def save_search(case_id: int, goal: str, query: str, results: List[Dict[str, Any]]) -> int:
    """Save a search to the database and return its ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO searches
    (id, search_goal, search_query, search_results)
    VALUES (?, ?, ?, ?)
    """, (
        case_id,
        goal,
        query,
        json.dumps(results)
    ))
    
    search_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return search_id

def save_relevant_results(search_id: int, websites: List[str], emails: List[str], reason: str) -> int:
    """Save relevant results to the database and return its ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO relevant_results
    (search_id, websites, emails, reason)
    VALUES (?, ?, ?, ?)
    """, (
        search_id,
        json.dumps(websites),
        json.dumps(emails),
        reason
    ))
    
    result_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return result_id

def get_case_details(case_id: int) -> Dict[str, Any]:
    """Get all details for a case including searches and relevant results."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get case parameters
    cursor.execute("""
    SELECT id, subject, location, budget, timeline, other_parameters
    FROM case_parameters
    WHERE id = ?
    """, (case_id,))
    
    case = dict(cursor.fetchone() or {})
    if not case:
        conn.close()
        return {}
    
    if 'other_parameters' in case and case['other_parameters']:
        case['others'] = json.loads(case['other_parameters'])
    
    # Get searches
    cursor.execute("""
    SELECT id, search_goal, search_query, search_results
    FROM searches
    WHERE id = ?
    ORDER BY id DESC
    """, (case_id,))
    
    searches = []
    for row in cursor.fetchall():
        search = dict(row)
        if 'search_results' in search and search['search_results']:
            search['results'] = json.loads(search['search_results'])
        
        # Get relevant results for this search
        cursor.execute("""
        SELECT id, websites, emails, reason
        FROM relevant_results
        WHERE search_id = ?
        """, (search['id'],))
        
        relevant_results = []
        for rr_row in cursor.fetchall():
            rr = dict(rr_row)
            if 'websites' in rr and rr['websites']:
                rr['websites'] = json.loads(rr['websites'])
            if 'emails' in rr and rr['emails']:
                rr['emails'] = json.loads(rr['emails'])
            relevant_results.append(rr)
        
        search['relevant_results'] = relevant_results
        searches.append(search)
    
    case['searches'] = searches
    conn.close()
    return case

# Tool implementations

@mcp.prompt()
def initial_prompt() -> str:
    return PROMPT_TEMPLATE

@mcp.prompt()
def precise_user_needs() -> str:
    return """
    Ask user about all the details required for the effective search and further actions with service providers or vendors
    Ask user about the subject, location, budget, timeline and other parameters crucial for finding the best options.
    Do it in maximum 3 qluestions.
    Return the updated case parameters.
    """


@mcp.tool()
def update_case_info(case_id: int, subject: str, location: str, budget: float, timeline: str, others: Optional[dict] = None) -> dict:
    """
    Update case parameters with gathered information from precise_user_needs tool.
    
    Args:
        case_id: The ID of the case to update
        subject: What product or service the user is looking for
        location: Geographic location for the search
        budget: Budget constraint for the purchase
        timeline: When the user needs the product/service
        others: Other relevant parameters as a JSON object
    """
    parameters = {
        'subject': subject,
        'location': location,
        'budget': budget,
        'timeline': timeline,
        'others': others or {}
    }
    
    success = update_case_parameters(case_id, parameters)
    if success:
        return {
            "success": True,
            "case_id": case_id,
            "message": f"Case {case_id} parameters updated successfully"
        }
    else:
        return {
            "success": False,
            "case_id": case_id,
            "message": f"Failed to update case {case_id}"
        }

@mcp.tool()
def get_case_info(case_id: int) -> dict:
    """
    Get information about a specific case.
    
    Args:
        case_id: The ID of the case to retrieve
    """
    case = get_case_details(case_id)
    if case:
        return {
            "success": True,
            "case": case
        }
    else:
        return {
            "success": False,
            "message": f"Case {case_id} not found"
        }


# Google Search API wrapper
def search_google(api_key, cse_id, query):
    """
    Perform the search using Google Custom Search API.
    
    Args:
        api_key (str): Google API key
        cse_id (str): Custom Search Engine ID
        query (str): The search query
        
    Returns:
        dict: Raw search results
    """
    base_url = "https://customsearch.googleapis.com/customsearch/v1"
    all_results = {"items": []}

    for start_index in [1, 11, 21]: 
        params = {
            'key': api_key,
            'cx': cse_id,
            'q': query,
            'num': 10,
            'start': start_index,
            'gl': 'pl',
            'hl': 'en',
            'safe': 'active',
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            if 'items' in data:
                all_results["items"].extend(data["items"])
                
                if start_index == 1 and 'searchInformation' in data:
                    all_results['searchInformation'] = data['searchInformation']
                if start_index == 1 and 'queries' in data:
                    all_results['queries'] = data['queries']

        except Exception as e:
            print(f"Search API error on page {start_index}: {str(e)}")
            if start_index == 1:
                return {"error": str(e)}

    return all_results

def format_search_results(data, query):
    """
    Format the search results.
    """
    if 'error' in data:
        return {
            "success": False,
            "error": data['error'],
            "results": []
        }

    if 'items' not in data:
        return {
            "success": True,
            "query": query,
            "total_results": 0,
            "results": []
        }

    formatted_results = []
    for index, item in enumerate(data['items']):
        result = {
            "id": index + 1,
            "title": item.get('title', 'No title'),
            "link": item.get('link', ''),
            "snippet": item.get('snippet', 'No description available'),
            "display_link": item.get('displayLink', '')
        }

        if 'pagemap' in item:
            pagemap = item['pagemap']

            if 'metatags' in pagemap and pagemap['metatags']:
                metatags = pagemap['metatags'][0]
                if 'og:description' in metatags:
                    result['og_description'] = metatags['og:description']

            if 'postaladdress' in pagemap:
                result['address'] = pagemap['postaladdress'][0].get('streetaddress', '')

            if 'localbusiness' in pagemap:
                business_info = pagemap['localbusiness'][0]
                result['business_name'] = business_info.get('name', '')
                result['business_phone'] = business_info.get('telephone', '')

            if 'cse_thumbnail' in pagemap and pagemap['cse_thumbnail']:
                thumbnail = pagemap['cse_thumbnail'][0]
                if 'src' in thumbnail:
                    result['thumbnail'] = thumbnail['src']

        formatted_results.append(result)

    response = {
        "success": True,
        "query": query,
        "total_results": int(data['searchInformation'].get('totalResults', 0)),
        "search_time": data['searchInformation'].get('searchTime', 0),
        "results": formatted_results
    }

    if 'queries' in data and 'nextPage' in data['queries']:
        response['next_page'] = data['queries']['nextPage'][0].get('startIndex', 0)

    return response

@mcp.tool()
async def search_vendors(case_id: int, search_query: str, search_goal: str) -> dict:
    """
    Search for vendors using Google Custom Search API.
    
    Args:
        case_id: The ID of the case
        search_query: The search query to execute
        search_goal: The goal of this search
    """
    # Get API credentials from environment variables
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("CUSTOM_SEARCH_API_KEY")
    cx = os.environ.get("GOOGLE_CSE_ID") or os.environ.get("CSE_ID")
    
    if not api_key or not cx:
        return {
            "success": False,
            "message": "Google API credentials not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables."
        }
    
    # Execute the search
    try:
        # Using the enhanced search function
        raw_results = search_google(api_key, cx, search_query)
        
        if 'error' in raw_results:
            return {
                "success": False,
                "message": f"Search error: {raw_results['error']}"
            }
            
        formatted_results = format_search_results(raw_results, search_query)
        
        if not formatted_results["success"]:
            return {
                "success": False,
                "message": formatted_results.get("error", "Unknown search error")
            }
        
        # Process and save results
        results = formatted_results["results"]
        
        # Save search to database
        search_id = save_search(case_id, search_goal, search_query, results)
        
        return {
            "success": True,
            "search_id": search_id,
            "results": results,
            "total_results": formatted_results["total_results"],
            "search_time": formatted_results["search_time"],
            "count": len(results)
        }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Error during search: {str(e)}"
        }

# Website scraper for contact information
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

@mcp.tool()
def validate_and_save_vendors(search_id: int, websites: List[str], emails: List[str], reason: str) -> dict:
    """
    Validate and save relevant vendor information.
    
    Args:
        search_id: The ID of the search these results are from
        websites: List of relevant website URLs
        emails: List of contact emails
        reason: Reason why these vendors are relevant
    """
    try:
        result_id = save_relevant_results(search_id, websites, emails, reason)
        return {
            "success": True,
            "result_id": result_id,
            "message": "Relevant vendors saved successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error saving relevant vendors: {str(e)}"
        }

# Additional tools for website scraping
@mcp.tool()
def scrape_contact_info(search_id: int, websites: List[str], max_pages_per_site: int = 10) -> dict:
    """
    Automatically scrape websites for contact information.
    
    Args:
        search_id: The ID of the search these results are from
        websites: List of websites to scrape
        max_pages_per_site: Maximum number of pages to scan per website
    """
    try:
        # Scrape the provided websites
        results = scrape_websites(websites, max_pages_per_site=max_pages_per_site)
        
        # Process and save results
        all_emails = []
        all_phones = []
        
        for domain, data in results.items():
            # Extract emails
            for email_info in data.get('emails', []):
                all_emails.append(email_info['value'])
            
            # Extract phones
            for phone_info in data.get('phones', []):
                all_phones.append(phone_info['value'])
        
        # Save unique contacts to database
        result_id = save_relevant_results(
            search_id, 
            websites, 
            list(set(all_emails)),
            "Automatically extracted from website scraping"
        )
        
        return {
            "success": True,
            "result_id": result_id,
            "websites_scraped": list(results.keys()),
            "emails_found": list(set(all_emails)),
            "phones_found": list(set(all_phones)),
            "detailed_results": results
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error scraping websites: {str(e)}"
        }

@mcp.tool()
def get_search_results(search_id: int) -> dict:
    """
    Get results for a specific search.
    
    Args:
        search_id: The ID of the search to retrieve
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get search information
        cursor.execute("""
        SELECT id, search_goal, search_query, search_results
        FROM searches
        WHERE id = ?
        """, (search_id,))
        
        search = cursor.fetchone()
        if not search:
            return {
                "success": False,
                "message": f"Search {search_id} not found"
            }
        
        search_data = dict(search)
        if 'search_results' in search_data and search_data['search_results']:
            search_data['results'] = json.loads(search_data['search_results'])
        
        # Get relevant results for this search
        cursor.execute("""
        SELECT id, websites, emails, reason
        FROM relevant_results
        WHERE search_id = ?
        """, (search_id,))
        
        relevant_results = []
        for row in cursor.fetchall():
            rr = dict(row)
            if 'websites' in rr and rr['websites']:
                rr['websites'] = json.loads(rr['websites'])
            if 'emails' in rr and rr['emails']:
                rr['emails'] = json.loads(rr['emails'])
            relevant_results.append(rr)
        
        search_data['relevant_results'] = relevant_results
        conn.close()
        
        return {
            "success": True,
            "search": search_data
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving search: {str(e)}"
        }

# Resource implementation
@mcp.resource("case://{case_id}")
def get_case_resource(case_id: str) -> str:
    """Provide case details as a resource."""
    try:
        case_details = get_case_details(int(case_id))
        if not case_details:
            return f"Case {case_id} not found"
        
        return json.dumps(case_details, indent=2)
    except Exception as e:
        return f"Error retrieving case: {str(e)}"


@mcp.resource("search://{search_id}")
def get_search_resource(search_id: str) -> str:
    """Provide search details as a resource."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, search_goal, search_query, search_results
        FROM searches
        WHERE id = ?
        """, (search_id,))
        
        search = cursor.fetchone()
        if not search:
            return f"Search {search_id} not found"
        
        search_data = dict(search)
        if 'search_results' in search_data and search_data['search_results']:
            search_data['results'] = json.loads(search_data['search_results'])
            
        conn.close()
        
        return json.dumps(search_data, indent=2)
    except Exception as e:
        return f"Error retrieving search: {str(e)}"

# Main execution
if __name__ == "__main__":
    mcp.run()