from __future__ import annotations

import httpx
import pytest

from dgro.services.scraper import (
    BlockedHostError,
    ContactScraper,
    check_public_host,
    clean_email,
    extract_contacts,
    is_directory,
    is_reserved_domain,
    normalize_url,
    pick_best_email,
    site_domain,
)


def test_url_helpers():
    assert normalize_url("firma.pl") == "https://firma.pl/"
    assert normalize_url("HTTP://WWW.Firma.pl/kontakt?x=1") == "http://www.firma.pl/kontakt?x=1"
    assert normalize_url("") == ""
    assert site_domain("https://www.firma.pl/kontakt") == "firma.pl"
    assert is_directory("pl-pl.facebook.com") and is_directory("panoramafirm.pl")
    assert not is_directory("firma.pl")
    assert is_reserved_domain("oferty@nova-demo.example") and is_reserved_domain("localhost")
    assert not is_reserved_domain("anna@firma.pl")


def test_clean_email_filters_junk():
    assert clean_email("mailto:Biuro@Firma.PL") == "biuro@firma.pl"
    assert clean_email("logo@2x.png") == ""
    assert clean_email("noreply@firma.pl") == ""
    assert clean_email("user@example.com") == ""
    assert clean_email("not an email") == ""


def test_extract_contacts_finds_obfuscated_and_structured_contacts():
    # Cloudflare-style protected email for "kontakt@firma.pl" (XOR key 0x42)
    key = 0x42
    encoded = f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in "kontakt@firma.pl")
    html = f"""
    <html><body>
      <a href="mailto:biuro@firma.pl?subject=Hi">Napisz</a>
      <span data-cfemail="{encoded}">[email protected]</span>
      <p>Sales: sales [at] firma [dot] pl</p>
      <p>Tel.: +48 12 345 67 89, NIP 677-000-00-00</p>
      <a href="tel:+48600100200">Zadzwoń</a>
      <img src="logo@2x.png">
      <script type="application/ld+json">{{"@type": "LocalBusiness", "email": "office@firma.pl"}}</script>
      <script>var x = "hidden@tracker.io";</script>
    </body></html>
    """
    emails, phones, _ = extract_contacts(html)
    assert set(emails) == {"biuro@firma.pl", "kontakt@firma.pl", "sales@firma.pl", "office@firma.pl"}
    assert "+48600100200" in phones and "+48 12 345 67 89" in phones
    assert not any("677" in p for p in phones)  # tax id is not labelled as a phone


def test_pick_best_email_prefers_site_role_addresses():
    emails = ["jan.kowalski@gmail.com", "info@firma.pl", "biuro@firma.pl", "marketing@firma.pl"]
    assert pick_best_email(emails, "firma.pl") == "biuro@firma.pl"
    assert pick_best_email(["jan@gmail.com"], "firma.pl") == "jan@gmail.com"
    assert pick_best_email([], "firma.pl") == ""


def site_transport() -> httpx.MockTransport:
    pages = {
        "/robots.txt": ("text/plain", "User-agent: *\nDisallow: /private\n"),
        "/": ("text/html", '<a href="/oferta">Oferta</a> <a href="/kontakt">Kontakt</a> <a href="/private">x</a>'),
        "/kontakt": ("text/html", '<p>Pisz: <a href="mailto:biuro@firma.pl">biuro@firma.pl</a></p>'
                                  '<a href="tel:+48 12 111 22 33">tel</a>'),
        "/oferta": ("text/html", "<p>Oferta</p>"),
        "/private": ("text/html", '<a href="mailto:secret@firma.pl">x</a>'),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path not in pages:
            return httpx.Response(404)
        content_type, body = pages[request.url.path]
        return httpx.Response(200, headers={"content-type": f"{content_type}; charset=utf-8"}, text=body)

    return httpx.MockTransport(handler)


def test_scraper_follows_contact_pages_and_respects_robots():
    with ContactScraper(max_pages=5, delay=0, allow_private=True, transport=site_transport()) as scraper:
        result = scraper.scrape("https://www.firma.pl")
    assert result.best_email == "biuro@firma.pl"
    assert "secret@firma.pl" not in result.emails
    assert result.pages[0] == "https://www.firma.pl/"
    assert "https://www.firma.pl/kontakt" in result.pages
    assert "https://www.firma.pl/private" not in result.pages
    assert result.phones == ["+48 12 111 22 33"]
    assert result.error == ""


def test_scraper_skips_reserved_demo_domains():
    with ContactScraper(delay=0) as scraper:
        result = scraper.scrape("https://nova-demo.example/")
    assert result.pages == [] and "reserved" in result.error


def test_private_addresses_are_blocked():
    with pytest.raises(BlockedHostError):
        check_public_host("127.0.0.1")
    with pytest.raises(BlockedHostError):
        check_public_host("localhost")
    with ContactScraper(delay=0, timeout=2) as scraper:
        result = scraper.scrape("http://192.168.1.1/")
    assert "non-public" in result.error and result.pages == []
