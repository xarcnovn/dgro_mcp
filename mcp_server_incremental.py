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
# Gmail manager imports
import base64
import pickle
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("incremental-case-search-manager")


PROMPT_TEMPLATE = """
You are a multi-agent system designed to help users find the best offers for products or services. The process involves three specialized agents working together:

1. Consultant (First Point of Contact)
	•	Acts as a friendly and professional advisor who gathers details from the user.
	•	Dynamically asks relevant questions to deeply understand the user's needs (e.g., budget, preferences, constraints).
	•	Must extract all necessary information in a maximum of five messages before passing the request to the Researcher.

Output:
	•	Google Search Query: A precise, 2-12 word phrase for finding vendors offering the desired service/product.

2. Researcher (Searcher and contact data Finder)
	•	Uses Google Custom Search API to find businesses offering the desired service/product.
	•	Returns a list of websites of businesses offering the desired service/product.
    - Then scrape the websites to find contact details.
Output:
    - Return a list of businesses with contact details. The list should include the website, email, and description of the business.

3. Negotiator (Communication Manager)
	•	Creates personalized email messages for vendors based on the case details.
	•	Sends emails to vendors, tracks communications, and manages responses.
	•	Analyzes responses and follows up appropriately.
	•	Provides summary of communications and recommends next actions.
Tools you use:
Use get_case tool to get the case details.
    - send_email_to_vendor: Send an initial outreach email to a vendor
    - get_unread_vendor_emails: Check for new responses from vendors
    - reply_to_vendor_email: Reply to a vendor's email
    - mark_email_as_read: Mark emails as read after processing
    - get_email_thread: View the full conversation with a vendor
    - get_case_communications: View all communications for a specific case

IMPORTANT - BEFORE SENDING ANY MESSAGE TO A VENDOR ASK USER FOR PERMISSION.

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
    
    # Create email_communications table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_communications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        vendor_email TEXT,
        vendor_name TEXT,
        vendor_website TEXT,
        subject TEXT,
        message_id TEXT,
        thread_id TEXT,
        email_type TEXT,
        email_content TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'sent',
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

# GMAIL INTEGRATION
# Gmail API scopes
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

@mcp.tool()
def send_email_to_vendor(case_id: int, vendor_email: str, subject: str, body: str, 
                         vendor_name: str = "", vendor_website: str = "") -> Dict[str, Any]:
    """
    Send an email to a vendor and track it in the database.
    
    Args:
        case_id: The ID of the case this email is associated with
        vendor_email: Email address of the vendor
        subject: Email subject line
        body: Email body in HTML format
        vendor_name: Name of the vendor (optional)
        vendor_website: Website of the vendor (optional)
        
    Returns:
        Dictionary with operation status, email ID if successful
    """
    try:
        # Get Gmail service
        service = get_gmail_service()
        
        # Create message
        message = MIMEMultipart()
        message['to'] = vendor_email
        message['subject'] = subject
            
        # Add body as HTML
        message.attach(MIMEText(body, 'html'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send message
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        message_id = sent_message['id']
        thread_id = sent_message.get('threadId', '')
        
        # Store in database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Verify the case exists
        cursor.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "message": f"Case with ID {case_id} not found"
            }
        
        # Insert email record
        cursor.execute("""
        INSERT INTO email_communications 
        (case_id, vendor_email, vendor_name, vendor_website, subject, message_id, thread_id, email_type, email_content, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_id,
            vendor_email,
            vendor_name,
            vendor_website,
            subject,
            message_id,
            thread_id,
            'initial_outreach',
            body,
            'sent'
        ))
        
        email_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "email_id": email_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "message": f"Email sent to {vendor_email} successfully and tracked with ID: {email_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error sending email: {str(e)}"
        }

def get_gmail_service():
    """
    Create a Gmail API service object.
    
    Returns:
        A Gmail API service object.
    """
    creds = None
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    
    # Check if token.pickle exists (stored credentials)
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials don't exist or are invalid, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                raise FileNotFoundError(f"Credentials file '{credentials_file}' not found. Run setup_gmail_api.py first.")
            
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

@mcp.tool()
def get_unread_vendor_emails(max_results: int = 10, associate_with_case: bool = True) -> Dict[str, Any]:
    """
    Retrieve unread emails that might be from vendors, and optionally associate them with cases.
    
    Args:
        max_results: Maximum number of emails to retrieve
        associate_with_case: Whether to attempt associating emails with existing cases
        
    Returns:
        Dictionary with operation status and unread emails
    """
    try:
        # Get Gmail service
        service = get_gmail_service()
        
        # Search for unread emails
        results = service.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            return {
                "success": True,
                "unread_emails": [],
                "message": "No unread messages found."
            }
        
        unread_emails = []
        
        for message in messages:
            msg = service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()
            
            # Extract headers
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
            
            # Extract thread ID
            thread_id = msg['threadId']
            
            # Format date
            try:
                parsed_date = datetime.strptime(date.split(' +')[0].strip(), '%a, %d %b %Y %H:%M:%S')
                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = date
            
            # Extract email body
            body = ""
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
                body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
            
            email_data = {
                'id': message['id'],
                'thread_id': thread_id,
                'sender': sender,
                'subject': subject,
                'date': formatted_date,
                'snippet': msg['snippet'],
                'body': body
            }
            
            # Try to find associated case if requested
            if associate_with_case:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Look for thread_id in email_communications
                cursor.execute("""
                SELECT ec.case_id, c.subject as case_subject FROM email_communications ec
                JOIN cases c ON ec.case_id = c.id
                WHERE ec.thread_id = ?
                LIMIT 1
                """, (thread_id,))
                
                case_row = cursor.fetchone()
                if case_row:
                    email_data['associated_case'] = {
                        'case_id': case_row['case_id'],
                        'case_subject': case_row['case_subject']
                    }
                
                # Try to infer from email content/subject if not found by thread
                if 'associated_case' not in email_data:
                    # Get all active cases
                    cursor.execute("SELECT id, subject FROM cases ORDER BY id DESC LIMIT 10")
                    cases = cursor.fetchall()
                    
                    # Simple heuristic: check if case subject appears in email subject or body
                    for case in cases:
                        if (case['subject'].lower() in subject.lower() or 
                            case['subject'].lower() in body.lower()):
                            email_data['potential_case'] = {
                                'case_id': case['id'],
                                'case_subject': case['subject'],
                                'confidence': 'medium'
                            }
                            break
                
                conn.close()
            
            unread_emails.append(email_data)
        
        return {
            "success": True,
            "unread_emails": unread_emails,
            "count": len(unread_emails),
            "message": f"Found {len(unread_emails)} unread emails"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving unread emails: {str(e)}"
        }

@mcp.tool()
def reply_to_vendor_email(case_id: int, message_id: str, reply_body: str, update_status: str = "ongoing") -> Dict[str, Any]:
    """
    Reply to a vendor email and track the communication in the database.
    
    Args:
        case_id: ID of the case associated with this communication
        message_id: ID of the message to reply to
        reply_body: Body of the reply message in HTML format
        update_status: New status for the communication (ongoing, completed, etc.)
        
    Returns:
        Dictionary with operation status and reply details
    """
    try:
        # Get Gmail service
        service = get_gmail_service()
        
        # Get the original message to extract headers
        original_message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='metadata',
            metadataHeaders=['Subject', 'From', 'To', 'Message-ID', 'References', 'In-Reply-To']
        ).execute()
        
        # Extract headers
        headers = original_message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        recipient = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
        message_id_header = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
        references = next((h['value'] for h in headers if h['name'].lower() == 'references'), message_id_header)
        
        # Extract email address from sender
        sender_email = re.search(r'<(.+?)>', sender)
        if sender_email:
            sender_email = sender_email.group(1)
        else:
            sender_email = sender
        
        # Extract thread ID
        thread_id = original_message['threadId']
        
        # Create reply message
        message = MIMEMultipart()
        message['to'] = sender_email
        
        # Check if subject already has Re: prefix
        if not subject.lower().startswith('re:'):
            message['subject'] = f"Re: {subject}"
        else:
            message['subject'] = subject
            
        # Set references and in-reply-to headers for proper threading
        if references:
            message['References'] = references
        message['In-Reply-To'] = message_id_header
        
        # Add body
        message.attach(MIMEText(reply_body, 'html'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send message
        sent_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message, 'threadId': thread_id}
        ).execute()
        
        reply_message_id = sent_message['id']
        
        # Store in database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Verify the case exists
        cursor.execute("SELECT id FROM cases WHERE id = ?", (case_id,))
        if not cursor.fetchone():
            conn.close()
            return {
                "success": False,
                "message": f"Case with ID {case_id} not found"
            }
        
        # Get vendor name and website if available from previous communications
        cursor.execute("""
        SELECT vendor_name, vendor_website FROM email_communications 
        WHERE case_id = ? AND vendor_email = ? 
        ORDER BY id DESC LIMIT 1
        """, (case_id, sender_email))
        
        vendor_info = cursor.fetchone()
        vendor_name = vendor_info[0] if vendor_info else ""
        vendor_website = vendor_info[1] if vendor_info else ""
        
        # Insert reply record
        cursor.execute("""
        INSERT INTO email_communications 
        (case_id, vendor_email, vendor_name, vendor_website, subject, message_id, thread_id, email_type, email_content, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_id,
            sender_email,
            vendor_name,
            vendor_website,
            message['subject'],
            reply_message_id,
            thread_id,
            'reply',
            reply_body,
            update_status
        ))
        
        email_id = cursor.lastrowid
        
        # Update status of previous messages in the same thread
        cursor.execute("""
        UPDATE email_communications 
        SET status = ? 
        WHERE thread_id = ? AND id != ?
        """, (update_status, thread_id, email_id))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "email_id": email_id,
            "message_id": reply_message_id,
            "thread_id": thread_id,
            "message": f"Reply sent to {sender_email} successfully and tracked with ID: {email_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error sending reply: {str(e)}"
        }

@mcp.tool()
def mark_email_as_read(message_id: str) -> Dict[str, Any]:
    """
    Mark an email as read.
    
    Args:
        message_id: ID of the message to mark as read
        
    Returns:
        Dictionary with operation status
    """
    try:
        # Get Gmail service
        service = get_gmail_service()
        
        # Remove UNREAD label
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        
        return {
            "success": True,
            "message": f"Message {message_id} marked as read"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error marking message as read: {str(e)}"
        }

@mcp.tool()
def get_email_thread(thread_id: str) -> Dict[str, Any]:
    """
    Get all messages in an email thread.
    
    Args:
        thread_id: ID of the thread to retrieve
        
    Returns:
        Dictionary with operation status and thread messages
    """
    try:
        # Get Gmail service
        service = get_gmail_service()
        
        # Get thread
        thread = service.users().threads().get(
            userId='me',
            id=thread_id
        ).execute()
        
        messages = []
        
        for message in thread['messages']:
            # Extract headers
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            recipient = next((h['value'] for h in headers if h['name'].lower() == 'to'), 'Unknown Recipient')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
            
            # Format date
            try:
                parsed_date = datetime.strptime(date.split(' +')[0].strip(), '%a, %d %b %Y %H:%M:%S')
                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                formatted_date = date
            
            # Extract email body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in message['payload'] and 'data' in message['payload']['body']:
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            
            messages.append({
                'id': message['id'],
                'sender': sender,
                'recipient': recipient,
                'subject': subject,
                'date': formatted_date,
                'snippet': message.get('snippet', ''),
                'body': body,
                'is_unread': 'UNREAD' in message.get('labelIds', [])
            })
        
        # Get case information from database if available
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT ec.case_id, c.subject as case_subject 
        FROM email_communications ec
        JOIN cases c ON ec.case_id = c.id
        WHERE ec.thread_id = ?
        LIMIT 1
        """, (thread_id,))
        
        case_row = cursor.fetchone()
        case_info = None
        
        if case_row:
            case_info = {
                'case_id': case_row['case_id'],
                'case_subject': case_row['case_subject']
            }
            
            # Get all communications in this thread from database
            cursor.execute("""
            SELECT id, email_type, status, sent_at 
            FROM email_communications
            WHERE thread_id = ?
            ORDER BY sent_at
            """, (thread_id,))
            
            communications = []
            for row in cursor.fetchall():
                communications.append(dict(row))
                
            case_info['communications'] = communications
            
        conn.close()
        
        return {
            "success": True,
            "thread_id": thread_id,
            "messages": messages,
            "message_count": len(messages),
            "case_info": case_info,
            "subject": messages[0]['subject'] if messages else "No messages found"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving email thread: {str(e)}"
        }

@mcp.tool()
def get_case_communications(case_id: int) -> Dict[str, Any]:
    """
    Get all email communications associated with a specific case.
    
    Args:
        case_id: ID of the case to retrieve communications for
        
    Returns:
        Dictionary with operation status and list of communications
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Verify the case exists
        cursor.execute("SELECT subject FROM cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        
        if not case_row:
            conn.close()
            return {
                "success": False,
                "message": f"Case with ID {case_id} not found"
            }
            
        case_subject = case_row['subject']
        
        # Get all email communications for this case
        cursor.execute("""
        SELECT ec.*, 
               COUNT(all_ec.id) as thread_message_count
        FROM email_communications ec
        LEFT JOIN email_communications all_ec ON ec.thread_id = all_ec.thread_id
        WHERE ec.case_id = ?
        GROUP BY ec.thread_id, ec.id
        ORDER BY ec.thread_id, ec.sent_at
        """, (case_id,))
        
        communications_rows = cursor.fetchall()
        
        # Group by thread_id for better organization
        threads = {}
        for row in communications_rows:
            comm = dict(row)
            thread_id = comm['thread_id']
            
            if thread_id not in threads:
                threads[thread_id] = {
                    'thread_id': thread_id,
                    'subject': comm['subject'],
                    'vendor_email': comm['vendor_email'],
                    'vendor_name': comm['vendor_name'],
                    'vendor_website': comm['vendor_website'],
                    'messages': [],
                    'last_update': comm['sent_at'],
                    'status': comm['status'],
                    'message_count': comm['thread_message_count']
                }
                
            threads[thread_id]['messages'].append({
                'id': comm['id'],
                'message_id': comm['message_id'],
                'email_type': comm['email_type'],
                'email_content': comm['email_content'],
                'sent_at': comm['sent_at'],
                'status': comm['status']
            })
                
        # Convert to list and sort by last_update (most recent first)
        thread_list = list(threads.values())
        thread_list.sort(key=lambda x: x['last_update'], reverse=True)
        
        # Count unique vendors
        cursor.execute("""
        SELECT COUNT(DISTINCT vendor_email) as vendor_count
        FROM email_communications
        WHERE case_id = ?
        """, (case_id,))
        
        vendor_count = cursor.fetchone()['vendor_count']
        
        conn.close()
        
        return {
            "success": True,
            "case_id": case_id,
            "case_subject": case_subject,
            "threads": thread_list,
            "thread_count": len(thread_list),
            "vendor_count": vendor_count,
            "message": f"Found {len(thread_list)} communication threads with {vendor_count} unique vendors"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error retrieving case communications: {str(e)}"
        } 



# Main execution
if __name__ == "__main__":
    mcp.run()