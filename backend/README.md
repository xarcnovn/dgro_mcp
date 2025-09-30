## Business Finder / Offer Negotiator – MCP Server

A multi-agent assistant that helps users find vendors/products, extract contact details, and manage email negotiations to secure the best offers. It integrates Google Custom Search, a focused website scraper, Gmail for outreach and follow‑ups, and SQLite for persistence.

## Purpose and business need
- **Automate discovery**: Find relevant businesses and products quickly using Google Custom Search.
- **Collect contacts**: Scrape websites for emails/phones, prioritizing contact pages.
- **Streamline outreach**: Send and track emails, manage threads, and structure vendor offers.
- **Centralize context**: Store cases, searches, communications, and offers in SQLite.

## Architecture
- **Primary MCP server**: `mcp_server_incremental.py` (recommended)
  - Tools to manage cases, users, searches, scraping, Gmail emails, and offers.
  - SQLite DB: `case_search.db` with tables `cases`, `users`, `searches`, `email_communications`, `offers`.
- **Prototype MCP server**: `mcp_server.py` (earlier version)
  - Simpler schema in `price_comparison.db` for `case_parameters`, `searches`, `relevant_results`.
  - Kept for reference; prefer the incremental server in day‑to‑day use.
- **Supporting modules**:
  - `scraper.py`: Standalone concurrent scraper used in servers.
  - `search.py`: Google Custom Search helpers.
  - `gmail_manager.py`: Standalone Gmail helpers (incremental server has inline equivalents).
- **External services**: Google Custom Search API; Gmail API (OAuth desktop flow).

## Data flow (happy path)
1. Capture user need → `create_case`/`update_case` (+ optional `create_user`).
2. Build a concise query → `execute_google_search` saves results to `searches`.
3. Extract contacts → `scrape_website_contacts` crawls same‑domain pages, prioritizing contact/about; returns emails/phones.
4. With user permission → `send_email_to_vendor` records `email_communications` entries.
5. Handle replies → `get_unread_vendor_emails`, `get_email_thread`, `reply_to_vendor_email`, `mark_email_as_read`.
6. Structure offers → `create_offer` / `update_offer`; view via `get_case_offers`.
7. Iterate until best offer is selected.

## Requirements
- Python 3.13+
- Google Cloud project with Custom Search API enabled and a CSE ID.
- Gmail API OAuth credentials (Desktop app) to a `credentials.json` file.

## Installation
Using uv (recommended):
```bash
cd /Users/karol/Desktop/projects/dgro_ios/dgro_mcp
uv sync
```

Using pip:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables
Place these in your shell or a local `.env` (dotenv is loaded):
- `GOOGLE_API_KEY` or `CUSTOM_SEARCH_API_KEY`: Google API key
- `GOOGLE_CSE_ID` or `CSE_ID`: Custom Search Engine ID
- `GOOGLE_CREDENTIALS_FILE`: Path to Gmail OAuth client secrets (e.g., `credentials.json`)

Example `.env`:
```env
GOOGLE_API_KEY=your_api_key
GOOGLE_CSE_ID=your_cse_id
GOOGLE_CREDENTIALS_FILE=credentials.json
```

## Running
### Run the recommended server (incremental)
```bash
python mcp_server_incremental.py
# or with MCP dev tools (inspector):
mcp dev mcp_server_incremental.py
```

### Prototype server (optional)
```bash
python mcp_server.py
```

## Database
- Incremental server uses `case_search.db` with tables:
  - `cases(id, subject, features, location, budget, timeline, additional_features)`
  - `users(id, case_id, name, email, phone)`
  - `searches(id, case_id, search_goal, search_query, search_results)`
  - `email_communications(id, case_id, vendor_email, vendor_name, vendor_website, subject, message_id, thread_id, email_type, email_content, sent_at, status)`
  - `offers(offer_id, case_id, status, price, timeline, accuracy, additional_details, communication_thread_id, vendor_email, created_at, updated_at)`
- Prototype server uses `price_comparison.db` with a simpler schema.

## MCP prompts and tools (incremental server)
- Prompts: `system_prompt` defines the 3‑agent flow: Consultant → Researcher → Negotiator.
- Case & user: `create_case`, `update_case`, `get_case`, `create_user`, `update_user`, `get_user`.
- Searches: `create_search`, `execute_google_search`, `update_search`, `get_search`.
- Scraping: `scrape_website_contacts` (extract emails/phones; concurrent crawling, retries, UA rotation).
- Gmail: `send_email_to_vendor`, `get_unread_vendor_emails`, `reply_to_vendor_email`, `mark_email_as_read`, `get_email_thread`, `get_case_communications`.
- Offers: `create_offer`, `update_offer`, `get_case_offers`.

## Gmail setup (first run)
1. In Google Cloud Console, create OAuth 2.0 Client ID (Desktop app) and download `credentials.json`.
2. Put it at the path referenced by `GOOGLE_CREDENTIALS_FILE`.
3. On first email action, a browser OAuth flow creates `token.pickle` locally.

## Troubleshooting
- Search credentials missing → tools return `success: False` with a message. Ensure `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` are set.
- Gmail credentials missing → a `FileNotFoundError` mentions `credentials.json`. Set `GOOGLE_CREDENTIALS_FILE` correctly.
- Rate limits / scraping issues → scraper logs non‑HTML responses and retry failures; reduce workers/pages or add delays.
- Thread‑to‑case linking is heuristic when `thread_id` is unknown; check `associated_case`/`potential_case` fields.
- Prototype server schema issues: its `searches` table and joins are simplified and may not match expectations; use the incremental server.
- `get_case_offers` note: ensure your case has offers created before expecting non‑empty `offers` list.

## Roadmap
- Automatic Negotiator flow (batch outreach, parallel negotiations) beyond manual tool calls.
- Stronger vendor validation and de‑duplication across search results.
- Better heuristics for mapping inbound emails to cases and extracting offer fields.

## License
MIT (see repository license of dependencies as applicable).


