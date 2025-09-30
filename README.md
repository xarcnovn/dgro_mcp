# Business Finder & Offer Negotiator

> A multi-agent MCP server that automates vendor discovery, contact extraction, and email negotiation to help you find the best deals.

## 🎯 Overview

This MCP (Model Context Protocol) server transforms how you find and negotiate with vendors. It combines intelligent search, automated contact discovery, and strategic email negotiations into a seamless workflow powered by three specialized AI agents.

### Key Features

- **🔍 Intelligent Search**: Leverage Google Custom Search API to find relevant businesses
- **📧 Contact Extraction**: Automatically scrape websites for emails and phone numbers
- **💬 Email Automation**: Send, track, and manage vendor communications via Gmail
- **💼 Offer Management**: Structure and compare vendor proposals in SQLite
- **🤖 Multi-Agent System**: Consultant → Researcher → Negotiator workflow

## 🏗️ Architecture

### Multi-Agent System

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Consultant  │ →  │  Researcher  │ →  │ Negotiator  │
│ Gathers     │    │  Finds       │    │  Manages    │
│ Requirements│    │  Contacts    │    │  Offers     │
└─────────────┘    └──────────────┘    └─────────────┘
```

**1. Consultant Agent**
- Collects user requirements through guided questions
- Extracts budget, preferences, location, and constraints
- Maximum 5 messages before handoff to Researcher

**2. Researcher Agent**
- Executes Google Custom Search based on requirements
- Scrapes vendor websites for contact information
- Prioritizes contact pages for better results

**3. Negotiator Agent**
- Drafts personalized outreach emails
- Tracks communication threads
- Extracts and structures offer details
- Recommends best options

### Technology Stack

- **MCP Server**: FastMCP for tool orchestration
- **Search**: Google Custom Search API
- **Email**: Gmail API (OAuth 2.0)
- **Database**: SQLite with 5 core tables
- **Scraping**: Concurrent web scraper with retry logic

## 📁 Project Structure

```
dgro_mcp/
├── mcp_server_incremental.py  # Main MCP server (recommended)
├── mcp_server.py               # Prototype server (legacy)
├── scraper.py                  # Concurrent web scraper
├── search.py                   # Google Search helpers
├── gmail_manager.py            # Gmail utilities
├── case_search.db              # Main database
├── credentials.json            # Gmail OAuth credentials
├── token.pickle                # Gmail auth token
└── requirements.txt            # Python dependencies
```

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Google Cloud project with:
  - Custom Search API enabled
  - Gmail API enabled
  - OAuth 2.0 credentials (Desktop app)

### Installation

Using `uv` (recommended):
```bash
cd dgro_mcp
uv sync
```

Using `pip`:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

1. **Create `.env` file**:
```env
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_custom_search_engine_id
GOOGLE_CREDENTIALS_FILE=credentials.json
```

2. **Set up Gmail API**:
   - Download OAuth 2.0 credentials from Google Cloud Console
   - Save as `credentials.json` in project root
   - First email action will trigger OAuth flow in browser

### Running the Server

**Recommended (incremental server)**:
```bash
python mcp_server_incremental.py
```

**With MCP Dev Tools**:
```bash
mcp dev mcp_server_incremental.py
```

**Legacy prototype server**:
```bash
python mcp_server.py
```

## 💡 Usage Workflow

### Happy Path Example

```
1. User expresses need
   ↓
2. create_case + create_user (capture requirements)
   ↓
3. execute_google_search (find vendors)
   ↓
4. scrape_website_contacts (extract emails/phones)
   ↓
5. send_email_to_vendor (initial outreach)
   ↓
6. get_unread_vendor_emails (check responses)
   ↓
7. create_offer (structure proposal)
   ↓
8. reply_to_vendor_email (negotiate)
   ↓
9. get_case_offers (compare options)
   ↓
10. Select best offer ✓
```

## 🛠️ Available Tools

### Case & User Management
- `create_case` - Initialize new case with requirements
- `update_case` - Modify case details
- `get_case` - Retrieve case with searches
- `create_user` - Add user contact information
- `update_user` - Modify user details
- `get_user` - Retrieve user information

### Search & Discovery
- `execute_google_search` - Search and save results
- `create_search` - Initialize search record
- `update_search` - Update search results
- `get_search` - Retrieve search details

### Contact Extraction
- `scrape_website_contacts` - Extract emails/phones from websites
  - Concurrent crawling (configurable workers)
  - Prioritizes contact pages
  - Retry logic with exponential backoff
  - User agent rotation

### Email Communication
- `send_email_to_vendor` - Send initial outreach
- `get_unread_vendor_emails` - Check new responses
- `reply_to_vendor_email` - Continue conversation
- `mark_email_as_read` - Update email status
- `get_email_thread` - View full conversation
- `get_case_communications` - All emails for case

### Offer Management
- `create_offer` - Record vendor proposal
- `update_offer` - Modify offer details
- `get_case_offers` - Compare all offers for case

## 📊 Database Schema

### Tables

**cases**
```sql
id, subject, features, location, budget, timeline, additional_features
```

**users**
```sql
id, case_id, name, email, phone
```

**searches**
```sql
id, case_id, search_goal, search_query, search_results
```

**email_communications**
```sql
id, case_id, vendor_email, vendor_name, vendor_website, 
subject, message_id, thread_id, email_type, email_content, 
sent_at, status
```

**offers**
```sql
offer_id, case_id, status, price, timeline, accuracy,
additional_details, communication_thread_id, vendor_email,
created_at, updated_at
```

## ⚙️ Configuration Options

### Scraper Settings
```python
scrape_website_contacts(
    urls=["https://example.com"],
    max_pages_per_site=10,  # Pages to crawl per domain
    max_workers=3           # Concurrent scraping threads
)
```

### Search Parameters
- Results per query: 30 (3 pages × 10 results)
- Geographic preference: Poland (`gl: 'pl'`)
- Language: English (`hl: 'en'`)
- Safe search: Active

## 🔒 Security Notes

- **Gmail OAuth**: Token stored in `token.pickle` (add to `.gitignore`)
- **API Keys**: Never commit `.env` file
- **Rate Limiting**: Scraper includes delays between requests
- **User Agents**: Rotated to avoid detection

## 🐛 Troubleshooting

### Search Credentials Missing
**Error**: Tools return `success: False`
**Solution**: Ensure `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` are set in `.env`

### Gmail Credentials Not Found
**Error**: `FileNotFoundError: credentials.json not found`
**Solution**: Download OAuth credentials from Google Cloud Console

### Scraping Issues
**Symptoms**: Non-HTML responses, retry failures
**Solutions**:
- Reduce `max_workers` or `max_pages_per_site`
- Check website's `robots.txt`
- Increase `delay_between_requests`

### Thread Linking Failures
**Issue**: Emails not associated with correct case
**Note**: System uses heuristic matching when `thread_id` unknown
**Check**: `associated_case` and `potential_case` fields

### Empty Offers List
**Issue**: `get_case_offers` returns no results
**Solution**: Ensure offers created via `create_offer` before querying

## 🗺️ Roadmap

- [ ] Automatic Negotiator flow (batch outreach)
- [ ] Parallel negotiation management
- [ ] Enhanced vendor validation
- [ ] De-duplication across search results  
- [ ] Improved email-to-case mapping heuristics
- [ ] Automatic offer field extraction from emails
- [ ] Support for additional communication channels

## 📝 License

MIT License - See repository for dependency licenses

## 🤝 Contributing

This project uses:
- Python 3.13+
- Type hints for better IDE support
- SQLite for simplicity and portability
- FastMCP for MCP protocol implementation

---

**Note**: The incremental server (`mcp_server_incremental.py`) is recommended for all use cases. The prototype server is kept for reference only.
