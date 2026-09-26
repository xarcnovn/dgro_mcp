from __future__ import annotations

import email
from datetime import datetime
from email import policy

from dgro.services import mail as mail_mod
from dgro.services.mail import (
    HeaderInfo,
    OutgoingEmail,
    SandboxMail,
    SmtpImapMail,
    build_mime,
    html_to_text,
    imap_date,
    parse_incoming,
    strip_quoted,
)

from .conftest import make_settings


def test_mime_roundtrip_keeps_threading_headers():
    out = OutgoingEmail(to_addr="biuro@firma.pl", subject="Zapytanie ofertowe: łazienka", body="Dzień dobry,\n\n- a\n- b",
                        from_addr="anna@example.org", from_name="Anna Nowak", message_id="<m1@example.org>",
                        in_reply_to="<v1@firma.pl>", references=["<m0@example.org>", "<v1@firma.pl>"])
    parsed = parse_incoming(bytes(build_mime(out)))
    assert parsed.message_id == "<m1@example.org>"
    assert parsed.in_reply_to == "<v1@firma.pl>"
    assert parsed.references == ["<m0@example.org>", "<v1@firma.pl>"]
    assert parsed.from_addr == "anna@example.org" and parsed.from_name == "Anna Nowak"
    assert parsed.subject == "Zapytanie ofertowe: łazienka"
    assert parsed.body.startswith("Dzień dobry,")


def test_strip_quoted_variants():
    polish = "Cena 12 500 zł.\n\nW dniu 12.09.2026 o 10:00, Anna <anna@x.pl> napisał(a):\n> prośba o wycenę"
    assert strip_quoted(polish) == "Cena 12 500 zł."
    gmail = "Price is 3000 EUR.\n\nOn Mon, 1 Sep 2026 at 10:00 Anna Nowak <\nanna@x.com> wrote:\n> hi"
    assert strip_quoted(gmail) == "Price is 3000 EUR."
    outlook = "Sure, next week.\n\nFrom: Anna <a@x.com>\nSent: Monday\nTo: Bob\n\nold text"
    assert strip_quoted(outlook) == "Sure, next week."
    assert strip_quoted("> only quoted") == "> only quoted"  # never return an empty body


def test_html_only_email_is_converted_to_text():
    raw = (b"From: Firma <biuro@firma.pl>\r\nTo: anna@example.org\r\nSubject: Oferta\r\nMessage-ID: <x@firma.pl>\r\n"
           b"Content-Type: text/html; charset=utf-8\r\n\r\n<div>Cena:<br><b>9 900 PLN</b></div><p>Termin 2 tyg.</p>")
    parsed = parse_incoming(raw)
    assert "9 900 PLN" in parsed.body and "Termin 2 tyg." in parsed.body
    assert "<b>" not in parsed.body
    assert html_to_text("<p>a</p><p>b</p>") == "a\nb"


def test_imap_date_is_locale_independent():
    assert imap_date(datetime(2026, 3, 5)) == "05-Mar-2026"


def test_sandbox_writes_eml(tmp_path):
    backend = SandboxMail(tmp_path / "outbox")
    note = backend.send(OutgoingEmail(to_addr="biuro@firma.pl", subject="Hi", body="Hello", from_addr="a@b.pl",
                                      message_id="<1@b.pl>"))
    files = list((tmp_path / "outbox").glob("*.eml"))
    assert len(files) == 1 and "not sent" in note
    msg = email.message_from_bytes(files[0].read_bytes(), policy=policy.default)
    assert msg["To"] == "biuro@firma.pl" and msg["Message-ID"] == "<1@b.pl>"


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.calls = []

    def ehlo(self):
        pass

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user))

    def send_message(self, msg, from_addr=None, to_addrs=None):
        FakeSMTP.sent.append((msg, from_addr, to_addrs, list(self.calls)))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_smtp_redirect_for_testing(tmp_path, monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(mail_mod.smtplib, "SMTP", FakeSMTP)
    settings = make_settings(tmp_path, email_mode="smtp", smtp_host="smtp.test", smtp_username="anna@example.org",
                             smtp_password="app-password", email_redirect_to="me@example.org")
    backend = SmtpImapMail(settings)
    note = backend.send(OutgoingEmail(to_addr="biuro@firma.pl", subject="Zapytanie", body="Hello",
                                      from_addr="anna@example.org", message_id="<1@example.org>"))
    msg, from_addr, to_addrs, calls = FakeSMTP.sent[0]
    assert to_addrs == ["me@example.org"] and from_addr == "anna@example.org"
    assert msg["To"] == "me@example.org" and msg["X-Dgro-Original-To"] == "biuro@firma.pl"
    assert msg["Subject"].startswith("[TEST for biuro@firma.pl]")
    assert calls == ["starttls", ("login", "anna@example.org")]
    assert "redirected" in note


def raw_email(uid: int, sender: str, subject: str, body: str, in_reply_to: str = "") -> bytes:
    headers = f"From: {sender}\r\nTo: anna@example.org\r\nSubject: {subject}\r\nMessage-ID: <in{uid}@vendor.pl>\r\n"
    if in_reply_to:
        headers += f"In-Reply-To: {in_reply_to}\r\nReferences: {in_reply_to}\r\n"
    return (headers + "Content-Type: text/plain; charset=utf-8\r\n\r\n" + body).encode()


class FakeIMAP:
    """Speaks just enough of imaplib's API, returning data in imaplib's response shapes."""

    messages: dict[int, bytes] = {}
    fetched_full: list[int] = []

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.readonly = None

    def login(self, user, password):
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=False):
        self.readonly = readonly
        return "OK", [str(len(self.messages)).encode()]

    def uid(self, command, *args):
        if command == "SEARCH":
            return "OK", [b" ".join(str(u).encode() for u in self.messages)]
        uids = [int(u) for u in (args[0].decode() if isinstance(args[0], bytes) else args[0]).split(",")]
        spec = args[1]
        response = []
        for uid in uids:
            raw = self.messages[uid]
            if "HEADER.FIELDS" in spec:
                msg = email.message_from_bytes(raw, policy=policy.default)
                wanted = ("Message-ID", "In-Reply-To", "References", "From")
                data = "".join(f"{h}: {msg[h]}\r\n" for h in wanted if msg[h]).encode() + b"\r\n"
                response += [(f"{uid} (UID {uid} BODY[HEADER.FIELDS] {{{len(data)}}}".encode(), data), b")"]
            else:
                FakeIMAP.fetched_full.append(uid)
                response += [(f"{uid} (UID {uid} BODY[] {{{len(raw)}}}".encode(), raw), b")"]
        return "OK", response

    def logout(self):
        return "BYE", []


def test_imap_fetch_only_downloads_wanted_messages(tmp_path, monkeypatch):
    FakeIMAP.messages = {
        1: raw_email(1, "Newsletter <news@shop.com>", "Promo", "Buy now"),
        2: raw_email(2, "Firma <biuro@firma.pl>", "Re: Zapytanie", "Cena 9 900 PLN", in_reply_to="<out1@example.org>"),
        3: raw_email(3, "Jan <jan@other.pl>", "Hello", "unrelated"),
    }
    FakeIMAP.fetched_full = []
    monkeypatch.setattr(mail_mod.imaplib, "IMAP4_SSL", FakeIMAP)
    settings = make_settings(tmp_path, email_mode="smtp", smtp_host="smtp.test", imap_host="imap.test",
                             smtp_username="anna@example.org", smtp_password="pw")
    backend = SmtpImapMail(settings)

    def wanted(h: HeaderInfo) -> bool:
        return "<out1@example.org>" in (h.in_reply_to, *h.references)

    results = backend.fetch_since(datetime(2026, 9, 1), wanted)
    assert FakeIMAP.fetched_full == [2]
    assert len(results) == 1
    assert results[0].from_addr == "biuro@firma.pl" and results[0].in_reply_to == "<out1@example.org>"
    assert "9 900 PLN" in results[0].body
