"""Deterministic offline stand-in for Claude.

Used for the demo mode (no API key) and in tests. It produces plausible output from the same context data the
real prompts are rendered from, so the whole workflow can be exercised without network access.
Demo vendors use the reserved `.example` TLD (RFC 2606), so they can never be contacted for real.
"""

from __future__ import annotations

import re
from typing import Any

from .base import ResearchResult, Source, T

CATEGORIES = [
    (r"bathroom|łazienk", "Bathroom renovation"),
    (r"kitchen|kuchni", "Kitchen fitting"),
    (r"roof|dach", "Roofing"),
    (r"window|okn", "Windows"),
    (r"paint|malowa", "Painting"),
    (r"cater", "Catering"),
    (r"mov(e|ing)|przeprowadz|transport", "Moving & transport"),
    (r"print|druk", "Printing"),
    (r"laptop|computer|komputer", "IT equipment"),
    (r"website|web page|stron[ay] (www|internetow)", "Web development"),
    (r"clean|sprząt", "Cleaning"),
    (r"solar|fotowolt|pv\b", "Solar installation"),
    (r"chair|furniture|desk|krzes|mebl|biurk", "Office furniture"),
]
CITIES = {
    "kraków": "PL", "krakow": "PL", "warszawa": "PL", "warsaw": "PL", "wrocław": "PL", "wroclaw": "PL",
    "gdańsk": "PL", "gdansk": "PL", "poznań": "PL", "poznan": "PL", "łódź": "PL", "lodz": "PL",
    "katowice": "PL", "berlin": "DE", "munich": "DE", "london": "GB", "manchester": "GB", "paris": "FR",
    "prague": "CZ", "vienna": "AT", "amsterdam": "NL",
}
LANG_BY_COUNTRY = {"PL": "pl", "DE": "de", "FR": "fr", "CZ": "cs", "AT": "de", "NL": "nl"}
CURRENCY_BY_COUNTRY = {"PL": "PLN", "DE": "EUR", "FR": "EUR", "AT": "EUR", "NL": "EUR", "CZ": "CZK", "GB": "GBP"}
VENDOR_NAMES = ["Nova", "Solidna Robota", "Prime Works", "Kowalski & Synowie", "Urban Craft", "Mistral"]
CURRENCY_TOKENS = {"zł": "PLN", "zl": "PLN", "pln": "PLN", "eur": "EUR", "€": "EUR", "euro": "EUR", "usd": "USD",
                   "$": "USD", "gbp": "GBP", "£": "GBP", "czk": "CZK", "kč": "CZK"}
PRICE_RE = re.compile(
    r"(?P<pre>€|\$|£|PLN|EUR|USD|GBP)?\s*(?P<num>\d{1,3}(?:[  .,]\d{3})+|\d+)(?:[.,](?P<dec>\d{2}))?\s*"
    r"(?P<post>zł|zl|pln|eur|euro|€|usd|\$|gbp|£|czk|kč)?",
    re.IGNORECASE,
)
TIMELINE_RE = re.compile(r"\b\d+\s*(?:-\s*\d+\s*)?(?:days?|weeks?|months?|dni|tygodni[ea]?|tyg\.?|miesięc\w*)\b",
                         re.IGNORECASE)
DECLINE_RE = re.compile(r"unfortunately|we (?:can ?not|can't|are unable)|not able to|niestety|nie jesteśmy w stanie|"
                        r"nie podejmiemy|nie realizujemy", re.IGNORECASE)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _category(text: str) -> str:
    for pattern, label in CATEGORIES:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return "Services"


def _city(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for city, country in CITIES.items():
        if city in lowered:
            return city.title(), country
    return "", ""


def parse_price(text: str) -> tuple[float | None, str]:
    """Return (amount, currency) for the most prominent price with a currency marker in `text`."""
    best: tuple[float, str] | None = None
    for m in PRICE_RE.finditer(text):
        marker = (m.group("pre") or m.group("post") or "").lower()
        if not marker:
            continue
        digits = re.sub(r"[  .,]", "", m.group("num"))
        amount = float(digits) + (float(m.group("dec")) / 100 if m.group("dec") else 0.0)
        if amount < 10:
            continue
        currency = CURRENCY_TOKENS.get(marker, marker.upper())
        if best is None or amount > best[0]:
            best = (amount, currency)
    return best if best else (None, "")


class FakeLLM:
    name = "fake"

    def structured(
        self,
        *,
        task: str,
        prompt: str,
        schema: type[T],
        effort: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> T:
        data = getattr(self, f"_{task}")(context or {})
        return schema.model_validate(data)

    def research(
        self,
        *,
        prompt: str,
        location: dict[str, str] | None = None,
        max_uses: int = 6,
        context: dict[str, Any] | None = None,
    ) -> ResearchResult:
        vendors = self._vendors(context or {})["vendors"]
        lines = [f"{v['name']} | {v['website']} | {v['city']} | {v['description']} | {v['email']}" for v in vendors]
        return ResearchResult(
            text="Demo research (simulated, no web access):\n" + "\n".join(lines),
            sources=[Source(url=v["website"], title=v["name"]) for v in vendors],
            searches=0,
        )

    # --- tasks -------------------------------------------------------------------------------------
    def _brief(self, ctx: dict[str, Any]) -> dict[str, Any]:
        case = ctx.get("case", {})
        text = case.get("request_text", "")
        category = _category(text)
        city, country = _city(f"{case.get('location', '')} {text}")
        first = re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])|\n", text.strip())[0] if text.strip() else category
        sentences = [s.strip(" -•\t") for s in re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])|\n|;", text)
                     if len(s.strip()) > 3]
        answered = {q["question"] for q in case.get("questions") or [] if q.get("answer")}
        questions = []
        if not answered:
            if not case.get("deadline"):
                questions.append("When should the work start, or by when do you need it delivered?")
            if not case.get("budget"):
                questions.append("What budget range do you have in mind?")
            questions.append("Will you supply any materials yourself, or should the vendor include everything?")
        language = LANG_BY_COUNTRY.get(country, "en")
        query = f"{category} {city}".strip()
        return {
            "title": (first[:57] + "...") if len(first) > 60 else first,
            "category": category,
            "summary": text.strip()[:400],
            "requirements": sentences[:6] or [text.strip()[:200]],
            "quantity": case.get("quantity", ""),
            "location": case.get("location", "") or city,
            "city": city,
            "country_code": country,
            "budget": case.get("budget", ""),
            "deadline": case.get("deadline", ""),
            "vendor_language": language,
            "search_queries": [query, f"{category} company {city}".strip()],
            "questions": questions,
        }

    def _vendors(self, ctx: dict[str, Any]) -> dict[str, Any]:
        case = ctx.get("case", {})
        n = min(int(ctx.get("max_vendors", 4)), 4)
        exclude = set(ctx.get("exclude_domains") or [])
        city = case.get("city") or "Local"
        category = case.get("category") or "Services"
        vendors = []
        for i, base in enumerate(VENDOR_NAMES):
            domain = f"{_slug(base)}-demo.example"
            if domain in exclude:
                continue
            vendors.append({
                "name": f"{base} (demo)",
                "website": f"https://www.{domain}/",
                "city": city,
                "description": f"{category} for private and business clients in {city}.",
                "relevance": "Offers exactly this service locally (simulated result).",
                # leave one vendor without an email to show the "no contact found" path
                "email": "" if i == 3 else f"oferty@{domain}",
                "phone": f"+48 600 100 {200 + i}",
            })
            if len(vendors) >= n:
                break
        return {"vendors": vendors}

    def _rfq(self, ctx: dict[str, Any]) -> dict[str, Any]:
        case = ctx.get("case", {})
        reqs = "\n".join(f"- {r}" for r in case.get("requirements") or [])
        name = case.get("contact_name") or "[Your name]"
        sig = "\n".join(x for x in [name, case.get("contact_phone", ""), case.get("contact_email", "")] if x)
        if case.get("vendor_language") == "pl":
            return {
                "subject": f"Zapytanie ofertowe: {case.get('title', '')}"[:80],
                "body": (
                    "Dzień dobry,\n\n"
                    f"szukam wykonawcy i chciałbym poprosić firmę {{vendor_name}} o przygotowanie oferty. "
                    f"{case.get('summary', '')}\n\nZakres:\n{reqs}\n\n"
                    "Proszę o podanie łącznej ceny (z podziałem, jeśli to możliwe), najbliższego terminu realizacji, "
                    "zakresu tego, co obejmuje cena, warunków płatności oraz ważności oferty. Porównuję kilka ofert.\n\n"
                    f"Pozdrawiam serdecznie\n{sig}"
                ),
            }
        return {
            "subject": f"Request for quote: {case.get('title', '')}"[:80],
            "body": (
                "Hello,\n\n"
                f"I'm looking for a provider and would like to ask {{vendor_name}} for a quote. "
                f"{case.get('summary', '')}\n\nScope:\n{reqs}\n\n"
                "Could you send me the total price (with a breakdown if possible), your earliest start or delivery "
                "date, what the price includes, payment terms and how long the offer is valid? I'm comparing a few "
                f"offers.\n\nKind regards,\n{sig}"
            ),
        }

    def _analyze_reply(self, ctx: dict[str, Any]) -> dict[str, Any]:
        case = ctx.get("case", {})
        body = ctx.get("email", {}).get("body", "")
        amount, currency = parse_price(body)
        timeline_match = TIMELINE_RE.search(body)
        declined = bool(DECLINE_RE.search(body)) and amount is None
        questions = [q.strip() for q in re.findall(r"[^.!?\n]*\?", body) if len(q.strip()) > 8][:3]
        missing = []
        if amount is None and not declined:
            missing.append("Total price")
        if not timeline_match and not declined:
            missing.append("Start date / timeline")
        budget_amount, _ = parse_price(case.get("budget", "") + " " + (currency or "pln"))
        if declined:
            action = "none"
        elif questions:
            action = "answer_questions"
        elif missing:
            action = "request_missing_info"
        elif amount and budget_amount and amount > budget_amount:
            action = "negotiate"
        else:
            action = "consider"
        fit = 0 if declined else (80 if amount and timeline_match else 55 if amount else 25)
        return {
            "summary": ("The vendor declined." if declined else
                        f"Offer of {amount:,.0f} {currency}." if amount else "Reply without a concrete price."),
            "is_quote": amount is not None,
            "declined": declined,
            "total_price": amount,
            "currency": currency or (CURRENCY_BY_COUNTRY.get(case.get("country_code", ""), "") if amount else ""),
            "price_basis": "fixed" if amount else "unknown",
            "price_text": f"{amount:,.0f} {currency}" if amount else "",
            "timeline": timeline_match.group(0) if timeline_match else "",
            "valid_until": "",
            "includes": [],
            "excludes": [],
            "conditions": "",
            "vendor_questions": questions,
            "missing_info": missing,
            "fit_score": fit,
            "fit_notes": "Estimated from the email text (demo mode).",
            "suggested_action": action,
        }

    def _draft_reply(self, ctx: dict[str, Any]) -> dict[str, Any]:
        case = ctx.get("case", {})
        intent = ctx.get("intent", "clarify")
        name = case.get("contact_name") or "[Your name]"
        extra = (ctx.get("instructions") or "").strip()
        pl = case.get("vendor_language") == "pl"
        texts = {
            "clarify": ("dziękuję za odpowiedź. Odpowiadając na pytania: [TODO: odpowiedzi]. "
                        "Proszę jeszcze o podanie terminu realizacji i ważności oferty.",
                        "thank you for your reply. To answer your questions: [TODO: answers]. Could you also "
                        "confirm the start date and how long the offer is valid?"),
            "negotiate": ("dziękuję za ofertę. Otrzymałem korzystniejsze propozycje cenowe - czy jest możliwość "
                          "obniżenia ceny lub lepszych warunków płatności?",
                          "thank you for the offer. I have received lower quotes - is there any flexibility on the "
                          "price or payment terms?"),
            "accept": ("dziękuję za ofertę - chciałbym ją przyjąć. Proszę o potwierdzenie terminu rozpoczęcia "
                       "i dalszych kroków.",
                       "thank you for the offer - I'd like to accept it. Please confirm the start date and next "
                       "steps."),
            "decline": ("dziękuję za przygotowanie oferty. Tym razem zdecydowałem się na inną propozycję.",
                        "thank you for preparing the offer. This time I have decided to go with another option."),
        }
        pl_text, en_text = texts.get(intent, texts["clarify"])
        greeting, closing = ("Dzień dobry,", "Pozdrawiam") if pl else ("Hello,", "Kind regards,")
        body = f"{greeting}\n\n{pl_text if pl else en_text}"
        if extra:
            body += f"\n\n{extra}"
        return {"body": f"{body}\n\n{closing}\n{name}"}

    def _compare(self, ctx: dict[str, Any]) -> dict[str, Any]:
        offers = ctx.get("offers", [])

        def score(o: dict[str, Any]) -> tuple[float, float]:
            price = o.get("total_price")
            return (0 if price is not None else 1, (price or 0) - (o.get("fit_score") or 0))

        ranked = sorted(offers, key=score)
        ranking = [
            {
                "vendor_id": o["vendor_id"],
                "rank": i + 1,
                "pros": [f"Price {o['total_price']:,.0f} {o.get('currency', '')}"] if o.get("total_price") else [],
                "cons": [f"Missing: {', '.join(o.get('missing_info') or [])}"] if o.get("missing_info") else [],
            }
            for i, o in enumerate(ranked)
        ]
        best = ranked[0] if ranked and ranked[0].get("total_price") is not None else None
        return {
            "headline": f"{best['vendor_name']} currently has the best offer." if best else "No complete offer yet.",
            "recommended_vendor_id": best["vendor_id"] if best else None,
            "rationale": "Ranked by total price, then by how well each offer covers the brief (demo mode).",
            "ranking": ranking,
            "risks": ["Offers may not cover the same scope - check includes/excludes before deciding."],
            "next_steps": ["Confirm the start date in writing with the chosen vendor."] if best else
            ["Ask vendors for a total price."],
        }
