"""Email transport.

- SandboxMail: nothing leaves the machine. Outgoing mail is written to data/outbox/*.eml; vendor replies are
  simulated from the UI. The default, so testing never emails real businesses.
- SmtpImapMail: sends over SMTP, collects replies over IMAP (read-only, messages are not marked as read).

Replies are matched to vendor threads through the standard In-Reply-To / References headers (RFC 5322 §3.6.4),
falling back to the sender address.
"""

from __future__ import annotations

import contextlib
import email
import html
import imaplib
import logging
import re
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Protocol

from bs4 import BeautifulSoup

from ..config import Settings

log = logging.getLogger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class OutgoingEmail:
    to_addr: str
    subject: str
    body: str
    from_addr: str
    from_name: str = ""
    reply_to: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)


@dataclass
class HeaderInfo:
    message_id: str
    from_addr: str
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)


@dataclass
class IncomingEmail:
    message_id: str
    from_addr: str
    from_name: str
    subject: str
    body: str
    body_full: str
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)
    date: datetime | None = None


class MailBackend(Protocol):
    name: str
    can_receive: bool

    def send(self, message: OutgoingEmail) -> str: ...

    def fetch_since(self, since: datetime, wanted: Callable[[HeaderInfo], bool]) -> list[IncomingEmail]: ...

    def check(self) -> list[tuple[bool, str]]: ...


# --- helpers ---------------------------------------------------------------------------------------
def new_message_id(sender: str) -> str:
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else "dgro.local"
    return make_msgid(idstring="dgro", domain=domain)


def text_to_html(text: str) -> str:
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    body = "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return f'<html><body style="font-family:Arial,Helvetica,sans-serif;font-size:14px">{body}</body></html>'


def html_to_text(markup: str) -> str:
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "blockquote"]):
        block.insert_after("\n")
    text = soup.get_text()
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t ]+", " ", text)).strip()


_SEPARATORS = [
    re.compile(r"^On .{4,300} wrote:$", re.IGNORECASE),
    re.compile(r"^(W dniu|Dnia) .{4,300} (napisał|napisała|napisał\(a\)|pisze)[^:]*:$", re.IGNORECASE),
    re.compile(r"^Am .{4,300} schrieb .{0,200}:$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*(Original Message|Wiadomość oryginalna|Ursprüngliche Nachricht)\s*-{2,}$", re.IGNORECASE),
    re.compile(r"^_{10,}$"),
]
_HEADER_BLOCK = re.compile(r"^(From|Od|Von):\s", re.IGNORECASE)
_HEADER_FOLLOW = re.compile(r"^(Sent|Date|Wysłano|Data|Gesendet|To|Do|An):\s", re.IGNORECASE)


def strip_quoted(text: str) -> str:
    """Remove quoted history from a reply so only the new text is analysed."""
    lines = text.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        joined = f"{stripped} {lines[i + 1].strip()}" if i + 1 < len(lines) else stripped
        if any(p.match(stripped) or p.match(joined) for p in _SEPARATORS):
            break
        if _HEADER_BLOCK.match(stripped) and any(_HEADER_FOLLOW.match(x.strip()) for x in lines[i + 1:i + 4]):
            break
        if stripped.startswith(">"):
            continue
        kept.append(line)
    result = "\n".join(kept).strip()
    return result or text.strip()


def build_mime(message: OutgoingEmail) -> EmailMessage:
    mime = EmailMessage()
    mime["From"] = formataddr((message.from_name, message.from_addr)) if message.from_name else message.from_addr
    mime["To"] = message.to_addr
    mime["Subject"] = message.subject
    mime["Date"] = formatdate(localtime=True)
    mime["Message-ID"] = message.message_id or new_message_id(message.from_addr)
    if message.reply_to:
        mime["Reply-To"] = message.reply_to
    if message.in_reply_to:
        mime["In-Reply-To"] = message.in_reply_to
    if message.references:
        mime["References"] = " ".join(message.references)
    mime.set_content(message.body)
    mime.add_alternative(text_to_html(message.body), subtype="html")
    return mime


def parse_incoming(raw: bytes) -> IncomingEmail:
    msg = email.message_from_bytes(raw, policy=policy.default)
    part = msg.get_body(preferencelist=("plain", "html"))
    content = ""
    if part is not None:
        try:
            content = part.get_content()
        except (LookupError, UnicodeDecodeError):
            content = part.get_payload(decode=True).decode("utf-8", errors="replace")
        if part.get_content_type() == "text/html":
            content = html_to_text(content)
    from_name, from_addr = parseaddr(str(msg.get("From", "")))
    date = None
    if msg.get("Date"):
        try:
            date = parsedate_to_datetime(str(msg["Date"]))
        except (TypeError, ValueError):
            date = None
    return IncomingEmail(
        message_id=str(msg.get("Message-ID", "")).strip(),
        from_addr=from_addr.lower(),
        from_name=from_name,
        subject=str(msg.get("Subject", "")),
        body=strip_quoted(content),
        body_full=content.strip(),
        in_reply_to=str(msg.get("In-Reply-To", "")).strip(),
        references=str(msg.get("References", "")).split(),
        date=date,
    )


def imap_date(value: datetime) -> str:
    return f"{value.day:02d}-{MONTHS[value.month - 1]}-{value.year}"


# --- backends --------------------------------------------------------------------------------------
class SandboxMail:
    name = "sandbox"
    can_receive = False

    def __init__(self, outbox_dir: Path):
        self.outbox_dir = outbox_dir

    def send(self, message: OutgoingEmail) -> str:
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        slug = re.sub(r"[^a-z0-9]+", "-", message.to_addr.lower()).strip("-")[:60]
        path = self.outbox_dir / f"{stamp}-{slug}.eml"
        path.write_bytes(bytes(build_mime(message)))
        return f"sandbox mode, not sent (saved as outbox/{path.name})"

    def fetch_since(self, since: datetime, wanted: Callable[[HeaderInfo], bool]) -> list[IncomingEmail]:
        return []

    def check(self) -> list[tuple[bool, str]]:
        return [(True, f"Sandbox mode: nothing is sent; emails are saved to {self.outbox_dir}.")]


class SmtpImapMail:
    name = "smtp"

    def __init__(self, settings: Settings):
        self.s = settings
        self.can_receive = bool(settings.imap_host and settings.imap_user and settings.imap_pass)

    # SMTP ----------------------------------------------------------------------------------------
    def _smtp(self) -> smtplib.SMTP:
        context = ssl.create_default_context()
        if self.s.smtp_security == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(self.s.smtp_host, self.s.smtp_port, timeout=30, context=context)
        else:
            client = smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30)
            client.ehlo()
            if self.s.smtp_security == "starttls":
                client.starttls(context=context)
                client.ehlo()
        if self.s.smtp_username:
            client.login(self.s.smtp_username, self.s.smtp_password)
        return client

    def send(self, message: OutgoingEmail) -> str:
        if not self.s.smtp_host:
            raise RuntimeError("DGRO_SMTP_HOST is not configured")
        mime = build_mime(message)
        recipient = message.to_addr
        note = f"sent to {recipient}"
        if self.s.email_redirect_to:
            recipient = self.s.email_redirect_to
            del mime["To"]
            mime["To"] = recipient
            mime["X-Dgro-Original-To"] = message.to_addr
            subject = mime["Subject"]
            del mime["Subject"]
            mime["Subject"] = f"[TEST for {message.to_addr}] {subject}"
            note = f"redirected to {recipient} (DGRO_EMAIL_REDIRECT_TO), intended for {message.to_addr}"
        with self._smtp() as client:
            client.send_message(mime, from_addr=message.from_addr, to_addrs=[recipient])
        return note

    # IMAP ----------------------------------------------------------------------------------------
    def _imap(self) -> imaplib.IMAP4:
        client = imaplib.IMAP4_SSL(self.s.imap_host, self.s.imap_port, ssl_context=ssl.create_default_context(),
                                   timeout=30)
        client.login(self.s.imap_user, self.s.imap_pass)
        return client

    def fetch_since(self, since: datetime, wanted: Callable[[HeaderInfo], bool]) -> list[IncomingEmail]:
        if not self.can_receive:
            return []
        client = self._imap()
        try:
            status, _ = client.select(f'"{self.s.imap_folder}"', readonly=True)
            if status != "OK":
                raise RuntimeError(f"cannot open IMAP folder {self.s.imap_folder}")
            status, data = client.uid("SEARCH", None, "SINCE", imap_date(since))
            uids = data[0].split() if status == "OK" and data and data[0] else []
            matches: list[bytes] = []
            for i in range(0, len(uids), 200):
                chunk = b",".join(uids[i:i + 200])
                status, resp = client.uid(
                    "FETCH", chunk, "(UID BODY.PEEK[HEADER.FIELDS (MESSAGE-ID IN-REPLY-TO REFERENCES FROM)])"
                )
                if status != "OK":
                    continue
                for item in resp:
                    if not isinstance(item, tuple):
                        continue
                    uid_match = re.search(rb"UID (\d+)", item[0])
                    if not uid_match:
                        continue
                    headers = email.message_from_bytes(item[1], policy=policy.default)
                    info = HeaderInfo(
                        message_id=str(headers.get("Message-ID", "")).strip(),
                        from_addr=parseaddr(str(headers.get("From", "")))[1].lower(),
                        in_reply_to=str(headers.get("In-Reply-To", "")).strip(),
                        references=str(headers.get("References", "")).split(),
                    )
                    if wanted(info):
                        matches.append(uid_match.group(1))
            results: list[IncomingEmail] = []
            for uid in matches:
                status, resp = client.uid("FETCH", uid, "(BODY.PEEK[])")
                if status == "OK":
                    raw = next((item[1] for item in resp if isinstance(item, tuple)), None)
                    if raw:
                        results.append(parse_incoming(raw))
            return results
        finally:
            with contextlib.suppress(imaplib.IMAP4.error, OSError):
                client.logout()

    def check(self) -> list[tuple[bool, str]]:
        results: list[tuple[bool, str]] = []
        try:
            with self._smtp():
                pass
            results.append((True, f"SMTP login to {self.s.smtp_host}:{self.s.smtp_port} works."))
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            results.append((False, f"SMTP {self.s.smtp_host}:{self.s.smtp_port} failed: {exc}"))
        if not self.can_receive:
            results.append((False, "IMAP is not configured - replies must be pasted in manually."))
            return results
        try:
            client = self._imap()
            status, _ = client.select(f'"{self.s.imap_folder}"', readonly=True)
            client.logout()
            results.append((status == "OK", f"IMAP login to {self.s.imap_host} works, folder "
                                             f"{self.s.imap_folder}: {status}."))
        except Exception as exc:  # noqa: BLE001
            results.append((False, f"IMAP {self.s.imap_host}:{self.s.imap_port} failed: {exc}"))
        return results


def build_mail(settings: Settings) -> MailBackend:
    if settings.email_mode == "smtp":
        return SmtpImapMail(settings)
    return SandboxMail(settings.outbox_dir)
