"""Find public contact details (emails, phones) on a vendor's website.

Polite by design: honest user agent, robots.txt respected, few pages per site, a delay between requests,
response size cap. Requests to private/loopback addresses are refused (SSRF guard), since URLs come from the web.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UA_TOKEN = "dgro"
USER_AGENT = "Mozilla/5.0 (compatible; dgro/0.2; +https://github.com/xarcnovn/dgro_mcp)"
MAX_BYTES = 2_000_000
RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost", ".local")

EMAIL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}")
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s().\-/]{7,20}\d")
PHONE_CONTEXT_RE = re.compile(
    r"(?:tel|phone|telefon|kom|mob|gsm|infolinia|call|zadzwoń|zadzwon)\w*\.?\s*:?\s*"
    r"((?:\+|00)?\d[\d\s().\-/]{7,20}\d)",
    re.IGNORECASE,
)
OBFUSCATED_AT = re.compile(r"\s*[\[\(\{]\s*(?:at|małpa|malpa)\s*[\]\)\}]\s*", re.IGNORECASE)
OBFUSCATED_DOT = re.compile(r"\s*[\[\(\{]\s*(?:dot|kropka)\s*[\]\)\}]\s*", re.IGNORECASE)

CONTACT_HINTS = ("kontakt", "contact", "o-nas", "about", "impressum", "zespol", "team", "wycena", "quote",
                 "oferta", "biuro", "reach")
ROLE_ORDER = ["biuro", "office", "kontakt", "contact", "info", "oferty", "zapytania", "wycena", "sales",
              "sprzedaz", "handel", "zamowienia", "orders", "hello", "serwis", "service"]
IGNORED_EMAIL_DOMAINS = {"example.com", "example.org", "domain.com", "email.com", "yourdomain.com", "sentry.io",
                         "wixpress.com", "sentry.wixpress.com", "sentry-next.wixpress.com", "godaddy.com",
                         "mysite.com", "twojadomena.pl", "domena.pl"}
BAD_EMAIL_ENDINGS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".ico", ".avif")
# Sites that list businesses but are not the business itself.
DIRECTORY_DOMAINS = {"facebook.com", "instagram.com", "linkedin.com", "youtube.com", "twitter.com", "x.com",
                     "tiktok.com", "pinterest.com", "google.com", "maps.google.com", "goo.gl", "yelp.com",
                     "tripadvisor.com", "wikipedia.org", "olx.pl", "allegro.pl", "oferteo.pl", "fixly.pl",
                     "panoramafirm.pl", "pkt.pl", "aleo.com", "gowork.pl", "cylex-polska.pl", "zumi.pl",
                     "firmy.net", "yellowpages.com", "yell.com", "trustpilot.com", "houzz.com", "checkatrade.com",
                     "bark.com", "thumbtack.com", "angi.com", "booking.com", "indeed.com", "pracuj.pl"}


class BlockedHostError(Exception):
    pass


@dataclass
class ContactResult:
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    best_email: str = ""
    error: str = ""


# --- URL helpers -----------------------------------------------------------------------------------
def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    if not parsed.hostname:
        return ""
    path = parsed.path or "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}" + (f"?{parsed.query}" if parsed.query else "")


def site_domain(url: str) -> str:
    host = (urlparse(normalize_url(url)).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_directory(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in DIRECTORY_DOMAINS)


def is_reserved_domain(domain_or_email: str) -> bool:
    domain = domain_or_email.rsplit("@", 1)[-1].lower().rstrip(".")
    return domain == "localhost" or domain.endswith(RESERVED_SUFFIXES)


def check_public_host(host: str) -> None:
    """Raise BlockedHostError if `host` is not a public internet host."""
    if not host or is_reserved_domain(host):
        raise BlockedHostError(f"{host!r} is not a public host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return  # not resolvable locally (e.g. behind an HTTP proxy): the request itself fails or goes via the proxy
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise BlockedHostError(f"{host} resolves to a non-public address ({ip})")


# --- extraction ------------------------------------------------------------------------------------
def clean_email(raw: str) -> str:
    email = unquote(raw or "").strip().strip(".,;:<>()[]'\"").lower()
    if email.startswith("mailto:"):
        email = email[7:]
    if not EMAIL_RE.fullmatch(email):
        return ""
    local, _, domain = email.partition("@")
    if email.endswith(BAD_EMAIL_ENDINGS) or domain in IGNORED_EMAIL_DOMAINS:
        return ""
    if local.startswith(("noreply", "no-reply", "donotreply")) or len(local) > 64:
        return ""
    return email


def _decode_cfemail(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i:i + 2], 16) ^ key) for i in range(2, len(encoded), 2))
    except ValueError:
        return ""


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not 9 <= len(digits) <= 15:
        return ""
    return re.sub(r"\s+", " ", raw.strip())


def extract_contacts(html: str) -> tuple[list[str], list[str], BeautifulSoup]:
    soup = BeautifulSoup(html, "html.parser")
    emails: list[str] = []
    phones: list[str] = []

    def add_email(value: str) -> None:
        email = clean_email(value)
        if email and email not in emails:
            emails.append(email)

    def add_phone(value: str) -> None:
        phone = _normalize_phone(value)
        if phone and phone not in phones:
            phones.append(phone)

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        lower = href.lower()
        if lower.startswith("mailto:"):
            for part in href[7:].split("?")[0].split(","):
                add_email(part)
        elif lower.startswith("tel:"):
            add_phone(unquote(href[4:]))
        elif "/cdn-cgi/l/email-protection#" in lower:
            add_email(_decode_cfemail(href.split("#", 1)[1]))
    for el in soup.select("[data-cfemail]"):
        add_email(_decode_cfemail(el.get("data-cfemail", "")))
    for script in soup.find_all("script", type="application/ld+json"):
        for match in EMAIL_RE.findall(script.get_text()):
            add_email(match)

    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = OBFUSCATED_DOT.sub(".", OBFUSCATED_AT.sub("@", text))
    for match in EMAIL_RE.findall(text):
        add_email(match)
    for match in PHONE_CONTEXT_RE.findall(text):
        add_phone(match)
    return emails, phones, soup


def pick_best_email(emails: list[str], domain: str) -> str:
    if not emails:
        return ""

    def rank(email: str) -> tuple[int, int, int]:
        local, _, email_domain = email.partition("@")
        same_site = bool(domain) and (email_domain == domain or email_domain.endswith("." + domain)
                                      or domain.endswith("." + email_domain))
        role = ROLE_ORDER.index(local) if local in ROLE_ORDER else len(ROLE_ORDER)
        return (0 if same_site else 1, role, len(email))

    return sorted(emails, key=rank)[0]


# --- crawler ---------------------------------------------------------------------------------------
class ContactScraper:
    def __init__(
        self,
        *,
        max_pages: int = 6,
        timeout: float = 12.0,
        allow_private: bool = False,
        delay: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ):
        self.max_pages = max_pages
        self.delay = delay
        self.allow_private = allow_private
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                     "Accept-Language": "pl,en;q=0.8"},
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            transport=transport,
            event_hooks={"request": [self._guard]},
        )

    def __enter__(self) -> ContactScraper:
        return self

    def __exit__(self, *exc: object) -> None:
        self.client.close()

    def _guard(self, request: httpx.Request) -> None:
        # Runs for every request, including each redirect hop.
        if not self.allow_private:
            check_public_host(request.url.host)

    def _get_html(self, url: str) -> tuple[str, str] | None:
        with self.client.stream("GET", url) as response:
            if response.status_code >= 400:
                return None
            if "html" not in response.headers.get("content-type", "").lower():
                return None
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_BYTES:
                    break
            raw = b"".join(chunks)
            encoding = response.encoding or "utf-8"
            return str(response.url), raw.decode(encoding, errors="replace")

    def _robots(self, start: str) -> RobotFileParser | None:
        parsed = urlparse(start)
        try:
            response = self.client.get(f"{parsed.scheme}://{parsed.netloc}/robots.txt", timeout=6)
        except (httpx.HTTPError, BlockedHostError):
            return None
        if response.status_code != 200:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser

    def scrape(self, website: str) -> ContactResult:
        start = normalize_url(website)
        result = ContactResult()
        if not start:
            result.error = "invalid website URL"
            return result
        domain = site_domain(start)
        if is_reserved_domain(domain):
            result.error = "reserved demo domain - not scanned"
            return result

        robots = self._robots(start)
        queue: deque[str] = deque([start])
        seen: set[str] = set()
        while queue and len(result.pages) < self.max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            if robots is not None and not robots.can_fetch(UA_TOKEN, url):
                continue
            if result.pages:
                time.sleep(self.delay)
            try:
                fetched = self._get_html(url)
            except BlockedHostError as exc:
                result.error = str(exc)
                break
            except httpx.HTTPError as exc:
                if not result.pages:
                    result.error = f"could not load {url}: {exc.__class__.__name__}"
                continue
            if fetched is None:
                continue
            final_url, html = fetched
            result.pages.append(final_url)
            emails, phones, soup = extract_contacts(html)
            result.emails += [e for e in emails if e not in result.emails]
            result.phones += [p for p in phones if p not in result.phones]

            contact_links: list[str] = []
            other_links: list[str] = []
            for a in soup.find_all("a", href=True):
                link = normalize_url(urljoin(final_url, a["href"].split("#")[0]))
                if not link or site_domain(link) != domain or link in seen:
                    continue
                if re.search(r"\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?)$", urlparse(link).path, re.IGNORECASE):
                    continue
                label = f"{link} {a.get_text(' ', strip=True)}".lower()
                (contact_links if any(h in label for h in CONTACT_HINTS) else other_links).append(link)
            for link in reversed(contact_links):
                queue.appendleft(link)
            if not result.emails:
                queue.extend(other_links[:10])

        if result.pages:
            result.error = ""
        result.best_email = pick_best_email(result.emails, domain)
        return result
