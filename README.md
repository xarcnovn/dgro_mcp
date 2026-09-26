# dgro · quotes

Describe what you need, and dgro gets you comparable quotes: it turns your request into a brief, finds local
vendors on the web, emails them a request for quote in your name (after you approve it), reads their replies,
extracts the offers and helps you compare, negotiate and decide.

Everything is organised around a **Case** (one thing you need quotes for), which moves through five stages:

| Stage | What happens | Who acts |
|---|---|---|
| 1 Brief | Claude structures your request, asks up to 4 questions that would change the quotes | you confirm |
| 2 Vendors | Claude web search finds businesses; dgro reads their sites for contact emails | automatic, you curate |
| 3 Outreach | One quote-request email (Claude drafts it in the vendors' language), one draft per vendor | **you approve each send** |
| 4 Quotes | Replies are matched to vendors and turned into structured offers (price, timeline, scope, gaps) | automatic |
| 5 Decision | Side-by-side comparison + recommendation; reply drafts to clarify, negotiate, accept or decline | you choose |

Runs entirely on your machine: a local web app, SQLite database and email through your own mailbox.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pip).

```bash
uv sync
uv run dgro serve          # http://127.0.0.1:8000
```

Without any configuration dgro starts in **demo mode**: AI steps return simulated results with demo vendors
(on the reserved `.example` domain) and email runs in **sandbox mode**, so you can click through a whole case,
paste vendor replies yourself, compare offers and choose one, with nothing leaving your machine.

With pip instead of uv: `python -m venv .venv && source .venv/bin/activate && pip install -e . && dgro serve`.

## Use Claude

```bash
cp .env.example .env       # set ANTHROPIC_API_KEY, DGRO_REQUESTER_NAME, DGRO_REQUESTER_EMAIL
uv run dgro doctor --live  # checks the key and model
uv run dgro serve
```

- Default model: `claude-opus-5` (`DGRO_MODEL` to change). Refusals are retried server-side on another model
  (`fallbacks="default"`); set `DGRO_REFUSAL_FALLBACK=false` to turn that off.
- Vendor search uses Claude's server-side web search tool, which must be enabled for your organisation in the
  Claude Console. It costs $10 per 1,000 searches plus tokens
  ([pricing](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)); dgro allows up to
  6 searches per vendor search (`DGRO_WEB_SEARCH_MAX_USES`).

## Send real email

Email stays in **sandbox** mode until you switch it: approved emails are written to `data/outbox/*.eml` and you
paste vendor replies into the case. For real sending and automatic reply collection, use any SMTP/IMAP mailbox:

```ini
DGRO_EMAIL_MODE=smtp
DGRO_SMTP_HOST=smtp.gmail.com
DGRO_SMTP_USERNAME=you@gmail.com
DGRO_SMTP_PASSWORD=xxxxxxxxxxxxxxxx   # Gmail: an app password
DGRO_IMAP_HOST=imap.gmail.com
DGRO_EMAIL_REDIRECT_TO=you+test@gmail.com   # recommended for the first run, see below
```

- Gmail needs 2-Step Verification and an [app password](https://support.google.com/accounts/answer/185833).
- `DGRO_EMAIL_REDIRECT_TO` delivers every outgoing email to you instead of the vendor (subject prefixed with
  the real recipient). Reply to it yourself as if you were the vendor and watch the offer appear in the case.
  Remove it when you are ready to contact real businesses.
- The inbox is checked every 3 minutes (read-only; nothing is marked as read) and only messages that reply to
  dgro's emails or come from a contacted vendor's address are imported. Replies are matched through the
  standard `In-Reply-To`/`References` headers ([RFC 5322 §3.6.4](https://www.rfc-editor.org/rfc/rfc5322#section-3.6.4)).
- `uv run dgro doctor --live` tests the SMTP and IMAP logins.

## How it is built

The old version exposed ~25 tools over MCP and relied on one long agent conversation to call them in the right
order. This version inverts that: **the workflow is plain Python and Claude is called inside individual steps.**

- **Workflow, not an agent loop.** The order of steps is fixed in code (`workflow/steps.py`); each step makes one
  narrow Claude call with a typed result. This is the "workflow" pattern Anthropic recommends when the task can
  be decomposed into predictable steps, keeping agents for open-ended problems
  ([Building effective agents](https://www.anthropic.com/research/building-effective-agents)). The only
  open-ended step, vendor research, uses Claude's server-side web search tool, which runs its own search loop.
- **Structured outputs.** Brief, vendor list, emails, offer extraction and comparison come back as Pydantic
  models via `client.beta.messages.parse`, so the app never parses free text.
- **Web search instead of Google Custom Search.** Google's Custom Search JSON API is closed to new customers and
  shuts down on 1 January 2027 ([Google](https://developers.google.com/custom-search/v1/overview)).
- **Durable background jobs.** Slow steps (Claude calls, scraping, sending, inbox sync) are rows in SQLite run by
  worker threads in the server process. They survive restarts, retry transient failures with backoff, surface
  errors on the case with a Retry button, and never re-send an email whose delivery state is unknown.
- **Human in the loop.** Nothing is emailed without your approval; drafts with `[TODO: …]` placeholders cannot
  be sent; the UI refreshes itself while jobs run but never over unsaved edits.
- **Offline test double.** `llm/fake_llm.py` implements the same interface deterministically; it powers demo
  mode and the test suite.

```
src/dgro/
  models.py            Case, Vendor, Message, Quote, Job, Event (SQLite via SQLAlchemy)
  schemas.py           structured outputs requested from Claude
  llm/                 anthropic_llm.py (SDK), fake_llm.py (offline), prompts.py
  services/            scraper.py (contact discovery), mail.py (sandbox, SMTP/IMAP)
  workflow/            steps.py (the pipeline), actions.py (user operations), jobs.py (queue + workers)
  web/                 FastAPI app, Jinja templates, a little vanilla JS (no build step)
  cli.py               dgro serve | doctor | sync-inbox
```

## Safety notes

- There is no login: dgro binds to `127.0.0.1`, rejects unknown `Host` headers (DNS rebinding) and cross-site
  form posts (CSRF). Do not expose it to a network.
- The contact scraper honours `robots.txt`, identifies itself, reads at most 6 pages per site with a delay, and
  refuses private/loopback addresses.
- Vendor emails and web content are passed to Claude as tagged, untrusted data, and every email it drafts is
  reviewed by you.
- Your data stays in `data/` (SQLite + outbox). Case details, web research and vendor replies are sent to the
  Claude API for processing.

## Development

```bash
uv run pytest              # 37 tests: workflow end to end, web UI, scraper, SMTP/IMAP, Claude API request shapes
uv run ruff check src tests
```

Schema changes that only add columns are applied automatically on startup; anything else needs a migration tool
such as Alembic. Set `ANTHROPIC_LOG=debug` to log raw API traffic.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Banner says demo mode | `ANTHROPIC_API_KEY` is not set in the environment or in `.env` in the folder you run `dgro` from |
| "authentication failed" on a step | wrong key; check with `dgro doctor --live`, then press Retry on the case |
| Vendor search fails: web search not enabled | enable web search in the Claude Console privacy settings, or add vendors manually |
| Few or no emails found for vendors | type the address in the Vendors tab, or press Rescan |
| SMTP/IMAP login fails | Gmail: use an app password (2-Step Verification required); check host/port/security |
| Port already in use | `uv run dgro serve --port 8001` |
