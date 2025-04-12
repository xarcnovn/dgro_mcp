import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def search(api_key, cse_id, query):
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

    print(f"\nSearch query: {query}")
    if 'searchInformation' in all_results:
        print(f"Total results: {all_results['searchInformation'].get('totalResults', '0')}")
        print(f"Search time: {all_results['searchInformation'].get('searchTime', '0')} seconds")
    print(f"Retrieved {len(all_results.get('items', []))} results")

    return all_results

def _format_results(data, query):
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

# Example usage (keeps the code functional without the removed search() function)
if __name__ == "__main__":
    api_key = os.getenv('CUSTOM_SEARCH_API_KEY')
    cse_id = os.getenv('CSE_ID')
    if not api_key or not cse_id:
        print("API credentials not found in environment variables.")
    else:
        query = "hydraulik Krakow"
        raw_results = search(api_key, cse_id, query)
        results = _format_results(raw_results, query)
        
        if results["success"]:
            print(f"Search query: {results['query']}")
            print(f"Found {results['total_results']} results in {results['search_time']} seconds")
            for result in results["results"]:
                print(f"\n{result['id']}. {result['title']}")
                print(f"URL: {result['link']}")
                print(f"Description: {result['snippet']}")
                if 'og_description' in result:
                    print(f"Additional info: {result['og_description']}")
                if 'business_name' in result and result['business_name']:
                    print(f"Business: {result['business_name']}")
                if 'business_phone' in result and result['business_phone']:
                    print(f"Phone: {result['business_phone']}")
                if 'address' in result and result['address']:
                    print(f"Address: {result['address']}")
        else:
            print(f"Search failed: {results['error']}")