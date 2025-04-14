import os
import json
import sqlite3
import requests
from typing import Dict, List, Optional, Any, Set, Tuple
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv
import re # Added for scraper
import random # Added for scraper
import time # Added for scraper
from urllib.parse import urljoin, urlparse # Added for scraper
from concurrent.futures import ThreadPoolExecutor, as_completed # Added for scraper
from dataclasses import dataclass, field # Added for scraper
from time import time as get_time # Added for scraper
from bs4 import BeautifulSoup # Added for scraper

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("incremental-case-search-manager")


PROMPT_TEMPLATE = """
You are a multi-agent system designed to help users find the best offers for products or services. The process involves two specialized agents working together:

1. Consultant (First Point of Contact)
	•	Acts as a friendly and professional advisor who gathers details from the user.
	•	Dynamically asks relevant questions to deeply understand the user's needs (e.g., budget, preferences, constraints).
	•	Must extract all necessary information in a maximum of five messages before passing the request to the Researcher.

Output:
	•	User's Task: A clear, structured summary of what the user wants, including all key details.
	•	Google Search Query: A precise, 2-12 word phrase for finding vendors offering the desired service/product.

2. Researcher (Searcher and contact data Finder)
	•	Uses Google Custom Search API to find businesses offering the desired service/product.
	•	Returns a list of websites of businesses offering the desired service/product.
    - Then scrape the websites to find contact details.
Output:
    - Return a list of businesses with contact details. The list should include the website, email, and description of the business.

Final Goal:
The system continuously refines the negotiation process until the user receives the best possible deal and makes a decision.
"""
@mcp.prompt()
def initial_prompt() -> str:
    return PROMPT_TEMPLATE


# SQLite database setup
DB_FILE = "case_search.db"

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create cases table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT,
        features TEXT,
        location TEXT,
        budget REAL,
        timeline TEXT,
        additional_features TEXT
    )
    ''')
    
    # Create searches table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        search_goal TEXT,
        search_query TEXT,
        search_results TEXT,
        FOREIGN KEY (case_id) REFERENCES cases (id)
    )
    ''')
    
    conn.commit()
    conn.close()
# Initialize DB when the server starts
init_db()

##DATABASE OPERATIONS TOOLS

@mcp.tool()
def create_case(subject: str = "", features: str = "", location: str = "", 
               budget: float = 0.0, timeline: str = "", additional_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new case record in the database.
    
    Args:
        subject: The subject or main topic of the case - user input
        features: Key features or requirements - user input
        location: Geographic location - user input
        budget: Budget amount - user input
        timeline: Expected timeline - user input
        additional_features: JSON object with any additional parameters - user input
    
    Returns:
        Dictionary with operation result and case ID
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Insert the case
        cursor.execute("""
        INSERT INTO cases 
        (subject, features, location, budget, timeline, additional_features)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            subject,
            features,
            location,
            budget,
            timeline,
            json.dumps(additional_features or {})
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

@mcp.tool()
def update_case(case_id: int, subject: Optional[str] = None, features: Optional[str] = None, 
               location: Optional[str] = None, budget: Optional[float] = None, 
               timeline: Optional[str] = None, additional_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Update an existing case with new information.
    Only update fields that are provided (not None).
    
    Args:
        case_id: ID of the case to update
        subject: Updated subject
        features: Updated features
        location: Updated location
        budget: Updated budget
        timeline: Updated timeline
        additional_features: Updated additional features
    
    Returns:
        Dictionary with operation result
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get current values
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        case = cursor.fetchone()
        
        if not case:
            conn.close()
            return {
                "success": False,
                "message": f"Case with ID {case_id} not found"
            }
        
        # Prepare update parameters
        case_data = {
            "subject": subject if subject is not None else case[1],
            "features": features if features is not None else case[2],
            "location": location if location is not None else case[3],
            "budget": budget if budget is not None else case[4],
            "timeline": timeline if timeline is not None else case[5],
        }
        
        # Handle additional features
        current_additional = json.loads(case[6] or '{}')
        if additional_features:
            current_additional.update(additional_features)
        case_data["additional_features"] = json.dumps(current_additional)
        
        # Update the case
        cursor.execute("""
        UPDATE cases 
        SET subject = ?, features = ?, location = ?, budget = ?, timeline = ?, additional_features = ?
        WHERE id = ?
        """, (
            case_data["subject"],
            case_data["features"],
            case_data["location"],
            case_data["budget"],
            case_data["timeline"],
            case_data["additional_features"],
            case_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"Case {case_id} updated successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to update case: {str(e)}"
        }

@mcp.tool()
def get_case(case_id: int) -> Dict[str, Any]:
    """
    Retrieve full case details including associated searches. When using this tool, pay attention to details of the case.
    Use it for:
    - constructing google search queries
    - creating a message for a service provider or vendor
    
    Args:
        case_id: ID of the case to retrieve
    
    Returns:
        Dictionary with case details and associated searches
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get case information
        cursor.execute("""
        SELECT id, subject, features, location, budget, timeline, additional_features
        FROM cases
        WHERE id = ?
        """, (case_id,))
        
        case_row = cursor.fetchone()
        if not case_row:
            conn.close()
            return {
                "success": False,
                "message": f"Case {case_id} not found"
            }
        
        case_data = dict(case_row)
        if 'additional_features' in case_data and case_data['additional_features']:
            case_data['additional_features'] = json.loads(case_data['additional_features'])
        
        # Get associated searches
        cursor.execute("""
        SELECT id, search_goal, search_query, search_results
        FROM searches
        WHERE case_id = ?
        ORDER BY id DESC
        """, (case_id,))
        
        searches = []
        for row in cursor.fetchall():
            search = dict(row)
            if 'search_results' in search and search['search_results']:
                search['search_results'] = json.loads(search['search_results'])
            searches.append(search)
        
        case_data['searches'] = searches
        conn.close()
        
        return {
            "success": True,
            "case": case_data
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving case: {str(e)}"
        }

@mcp.tool()
def create_search(case_id: int, search_goal: str, search_query: str, 
                 search_results: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Create a new search associated with a case. Retrieve how usually effective google search queries look like, but be concise. 
    Use it for:
    - searching for service providers or vendors
    - searching for products or services
    - searching for information about the case
    
    Args:
        case_id: ID of the case this search belongs to
        search_goal: The goal or purpose of the search
        search_query: The query string used for the search
        search_results: Optional initial search results
    
    Returns:
        Dictionary with operation result and search ID
    """
    try:
        # Verify the case exists
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "message": f"Case with ID {case_id} not found"
            }
        
        # Insert the search
        cursor.execute("""
        INSERT INTO searches
        (case_id, search_goal, search_query, search_results)
        VALUES (?, ?, ?, ?)
        """, (
            case_id,
            search_goal,
            search_query,
            json.dumps(search_results or [])
        ))
        
        search_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "search_id": search_id,
            "message": f"New search created with ID: {search_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to create search: {str(e)}"
        }

@mcp.tool()
def update_search(search_id: int, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update a search with search results.
    
    Args:
        search_id: ID of the search to update
        search_results: The search results to add/update
    
    Returns:
        Dictionary with operation result
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Verify the search exists
        cursor.execute("SELECT id, search_results FROM searches WHERE id = ?", (search_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {
                "success": False,
                "message": f"Search with ID {search_id} not found"
            }
        
        # Update the search results
        existing_results = json.loads(result[1] or '[]')
        
        # Combine existing results with new ones if needed
        # In this implementation, we're replacing existing results
        # Change this logic if you want to append instead
        
        cursor.execute("""
        UPDATE searches 
        SET search_results = ?
        WHERE id = ?
        """, (
            json.dumps(search_results),
            search_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"Search {search_id} updated successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to update search: {str(e)}"
        }

@mcp.tool()
def get_search(search_id: int) -> Dict[str, Any]:
    """
    Retrieve full search details.
    Use this tool for:
    - analyzing search results
    - creating a list of vendors to reach out to
        
    Args:
        search_id: ID of the search to retrieve
    
    Returns:
        Dictionary with search details
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get search information
        cursor.execute("""
        SELECT id, case_id, search_goal, search_query, search_results
        FROM searches
        WHERE id = ?
        """, (search_id,))
        
        search_row = cursor.fetchone()
        if not search_row:
            conn.close()
            return {
                "success": False,
                "message": f"Search {search_id} not found"
            }
        
        search_data = dict(search_row)
        if 'search_results' in search_data and search_data['search_results']:
            search_data['search_results'] = json.loads(search_data['search_results'])
        
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

# GOOGLE SEARCH TOOL
# Integrated from search.py

@mcp.tool()
def execute_google_search(case_id: int, search_goal: str, search_query: str) -> Dict[str, Any]:
    """
    Execute a Google search, save the results to the database, and return them.
    This tool combines:
    1. Executing a Google search via the Custom Search API
    2. Formatting the search results
    3. Saving the results to the database
    
    Args:
        case_id: ID of the case to associate this search with
        search_goal: The goal or purpose of this search
        search_query: The query string to search for
    
    Returns:
        Dictionary with search results and operation status
    """
    try:
        # Get API credentials from environment variables
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("CUSTOM_SEARCH_API_KEY")
        cse_id = os.getenv("GOOGLE_CSE_ID") or os.getenv("CSE_ID")
        
        if not api_key or not cse_id:
            return {
                "success": False,
                "message": "Google API credentials not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables."
            }
        
        # 1. Execute the search using Google API
        raw_results = _search_google(api_key, cse_id, search_query)
        
        if 'error' in raw_results:
            return {
                "success": False,
                "message": f"Search error: {raw_results['error']}"
            }
            
        # 2. Format the search results
        formatted_results = _format_search_results(raw_results, search_query)
        
        if not formatted_results["success"]:
            return {
                "success": False,
                "message": formatted_results.get("error", "Unknown search error")
            }
        
        # 3. Save the search and results to the database
        results = formatted_results["results"]
        
        # Verify the case exists
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "message": f"Case with ID {case_id} not found"
            }
        
        # Insert the search
        cursor.execute("""
        INSERT INTO searches
        (case_id, search_goal, search_query, search_results)
        VALUES (?, ?, ?, ?)
        """, (
            case_id,
            search_goal,
            search_query,
            json.dumps(results)
        ))
        
        search_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "search_id": search_id,
            "query": search_query,
            "total_results": formatted_results["total_results"],
            "search_time": formatted_results["search_time"],
            "results": results,
            "count": len(results),
            "message": f"Search executed and saved with ID: {search_id}"
        }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Error during search: {str(e)}"
        }

# Helper functions for the search tool

def _search_google(api_key, cse_id, query):
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

def _format_search_results(data, query):
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

# SCRAPER TOOL AND HELPERS (Integrated from scraper.py)

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

@mcp.tool()
def scrape_website_contacts(urls: List[str], max_pages_per_site: int = 10, max_workers: int = 3) -> Dict[str, Any]:
    """
    Scrape multiple websites concurrently to find contact information (emails, phone numbers).

    Args:
        urls: A list of website URLs to scrape.
        max_pages_per_site: Maximum number of pages to crawl on each site. Defaults to 10.
        max_workers: Maximum number of concurrent workers for scraping. Defaults to 3.

    Returns:
        A dictionary where keys are the domain names and values are dictionaries containing:
        - 'domain': The scraped domain.
        - 'emails': A list of found email addresses, each with 'value' and 'found_on' (list of URLs).
        - 'phones': A list of found phone numbers, each with 'value' and 'found_on' (list of URLs).
        - 'pages_scanned': A list of URLs scanned on the site.
        - 'scan_time': Time taken for scanning the site.
        - 'error': An error message if scraping failed for a specific domain.
        Includes a top-level 'success' key (True if the overall operation started, False otherwise) 
        and potentially a 'message' key for overall errors.
    """
    try:
        # Validate and normalize URLs
        valid_urls = []
        for url in urls:
            if url:
                # Normalize URL
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                valid_urls.append(url)
        
        if not valid_urls:
            return {"success": False, "message": "No valid URLs provided."}
        
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

        return {
            "success": True,
            "results": results
        }
    except Exception as e:
         return {
            "success": False,
            "message": f"Failed to run website scraping: {str(e)}"
        }

# Main execution
if __name__ == "__main__":
    mcp.run() 