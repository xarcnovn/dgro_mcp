# Business Finder & Offer Negotiator

Multi-agent MCP server that automates vendor discovery, contact extraction, and email negotiation.

## Features

- **Search**: Google Custom Search API integration
- **Contact Extraction**: Automated website scraping for emails/phones
- **Email Automation**: Gmail integration for vendor communications
- **Offer Management**: SQLite-based proposal tracking
- **Multi-Agent Workflow**: Consultant → Researcher → Negotiator

## Architecture

**Three-Agent System**: Consultant (gathers requirements) → Researcher (finds contacts) → Negotiator (manages offers)

**Stack**: FastMCP, Google Custom Search API, Gmail API (OAuth 2.0), SQLite, concurrent web scraper

## Project Structure

- `mcp_server_incremental.py` - Main MCP server (recommended)
- `scraper.py` - Web scraper | `search.py` - Search helpers | `gmail_manager.py` - Gmail utilities
- `case_search.db` - SQLite database
- `credentials.json` + `token.pickle` - Gmail OAuth (not in git)

## Quick Start

**Prerequisites**: Python 3.13+, Google Cloud project with Custom Search API + Gmail API + OAuth 2.0 credentials

**Install**:
```bash
uv sync  # or: pip install -r requirements.txt
```

**Configure** `.env`:
```env
GOOGLE_API_KEY=your_key
GOOGLE_CSE_ID=your_cse_id
GOOGLE_CREDENTIALS_FILE=credentials.json
```

Add `credentials.json` (OAuth from Google Cloud Console). First email action triggers OAuth flow.

**Run**:
```bash
python mcp_server_incremental.py
# or: mcp dev mcp_server_incremental.py
```

## Workflow

`create_case` → `execute_google_search` → `scrape_website_contacts` → `send_email_to_vendor` → `get_unread_vendor_emails` → `create_offer` → `reply_to_vendor_email` → `get_case_offers` → select best offer

## Available Tools

**Case/User**: `create_case`, `update_case`, `get_case`, `create_user`, `update_user`, `get_user`
**Search**: `execute_google_search`, `create_search`, `update_search`, `get_search`
**Scraping**: `scrape_website_contacts` (concurrent, contact page priority, retry logic)
**Email**: `send_email_to_vendor`, `get_unread_vendor_emails`, `reply_to_vendor_email`, `mark_email_as_read`, `get_email_thread`, `get_case_communications`
**Offers**: `create_offer`, `update_offer`, `get_case_offers`

## Database

**5 Tables**: `cases` (requirements), `users` (contact info), `searches` (queries/results), `email_communications` (threads), `offers` (proposals)

## Configuration

**Scraper**: `max_pages_per_site=10`, `max_workers=3`
**Search**: 30 results/query, Poland region, English language

## Security

Add to `.gitignore`: `token.pickle`, `.env`. OAuth token auto-generated on first email action.

## Troubleshooting

- **Missing credentials**: Set `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` in `.env`, add `credentials.json`
- **Scraping failures**: Reduce `max_workers` or check `robots.txt`
- **Thread linking**: Check `associated_case`/`potential_case` fields

## Roadmap

Automatic batch outreach, parallel negotiations, vendor validation, deduplication, improved email-to-case mapping, automatic offer extraction

## License

MIT
