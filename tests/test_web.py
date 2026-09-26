"""The web UI through HTTP, the way a browser drives it."""

from __future__ import annotations

import re

from dgro.models import Case, Message


def post(client, url, data=None, **kwargs):
    return client.post(url, data=data or {}, follow_redirects=False, **kwargs)


def location(response) -> str:
    assert response.status_code == 303, response.text
    return response.headers["location"]


def test_pages_render(client):
    assert client.get("/healthz").json() == {"ok": True}
    home = client.get("/")
    assert home.status_code == 200 and "Start your first case" in home.text
    assert "Demo mode" in home.text
    assert client.get("/cases/new").status_code == 200
    assert "Sandbox" in client.get("/settings").text
    assert client.get("/cases/999").status_code == 404
    assert "Sandbox mode" in client.post("/settings/test-email").text


def test_new_case_validation(client):
    response = post(client, "/cases", {"request_text": "hi"})
    assert response.status_code == 400 and "at least a sentence" in response.text


def test_security_middleware(client):
    blocked = post(client, "/cases", {"request_text": "x" * 20}, headers={"Origin": "https://evil.example"})
    assert blocked.status_code == 403
    assert post(client, "/cases", {"request_text": "x" * 20}, headers={"Origin": "null"}).status_code == 403
    assert client.get("/", headers={"Host": "attacker.example"}).status_code == 400
    same_site = post(client, "/cases", {"request_text": "Need 20 office chairs in Wrocław."},
                     headers={"Origin": "http://testserver"})
    assert same_site.status_code == 303


def test_case_flow_through_the_ui(client, rt):
    url = location(post(client, "/cases", {"request_text": "Office chairs: 20 ergonomic chairs for our office in "
                                                           "Wrocław, delivery and assembly included.",
                                           "location": "Wrocław", "budget": "30 000 PLN"}))
    case_id = int(re.search(r"/cases/(\d+)", url).group(1))
    page = client.get(url)
    assert "Drafting the brief" in page.text and 'data-busy="1"' in page.text
    status = client.get(f"/cases/{case_id}/status").json()
    assert status["busy"] and status["jobs"] == ["Drafting the brief"]

    rt.worker.run_pending()
    page = client.get(f"/cases/{case_id}?tab=brief")
    assert "Questions that would sharpen the quotes" in page.text and "Office furniture" in page.text
    assert not client.get(f"/cases/{case_id}/status").json()["busy"]

    with rt.session() as db:
        case = db.get(Case, case_id)
        form = {"title": case.title, "summary": case.summary, "requirements": "\n".join(case.requirements),
                "country_code": case.country_code, "vendor_language": case.vendor_language,
                "search_queries": "\n".join(case.search_queries), "contact_name": "Anna Nowak",
                "contact_email": "anna@example.org", "answer_0": "Vendor includes everything", "action": "confirm"}
    assert "tab=vendors" in location(post(client, f"/cases/{case_id}/brief", form))
    rt.worker.run_pending()

    vendors_page = client.get(f"/cases/{case_id}?tab=vendors").text
    assert "Nova (demo)" in vendors_page and "No email found" in vendors_page
    with rt.session() as db:
        case = db.get(Case, case_id)
        missing = next(v for v in case.vendors if not v.email)
        ids = [v.id for v in case.vendors if v.email]
    # give the vendor without an email one by hand
    assert "Saved" in location(post(client, f"/cases/{case_id}/vendors/{missing.id}",
                                    {"op": "save", "email": "biuro@kowalski.pl"}))
    bad = location(post(client, f"/cases/{case_id}/vendors/{missing.id}", {"op": "save", "email": "nope"}))
    assert "error=" in bad

    outreach = client.get(f"/cases/{case_id}?tab=outreach").text
    assert "Quote request email" in outreach and "{vendor_name}" in outreach
    with rt.session() as db:
        case = db.get(Case, case_id)
        rfq = {"rfq_subject": case.rfq_subject, "rfq_body": case.rfq_body + "\n\nPS. Edited by hand."}
    response = client.post(f"/cases/{case_id}/drafts", data={**rfq, "vendor_ids": [*ids, missing.id]},
                           follow_redirects=False)
    assert "4+draft" in location(response)
    outreach = client.get(f"/cases/{case_id}?tab=outreach").text
    assert "Drafts awaiting your approval" in outreach and "PS. Edited by hand." in outreach

    with rt.session() as db:
        draft = db.get(Case, case_id).draft_messages[0]
    location(post(client, f"/cases/{case_id}/messages/{draft.id}", {"op": "discard"}))
    assert "3+email" in location(post(client, f"/cases/{case_id}/messages/send-all"))
    rt.worker.run_pending()

    with rt.session() as db:
        case = db.get(Case, case_id)
        contacted = [m.vendor for m in case.sent_messages]
    assert len(contacted) == 3
    for vendor, text in zip(contacted[:2], ["Total 27 400 PLN incl. delivery, 3 weeks.",
                                            "We offer 24 900 PLN, delivery in 4 weeks."], strict=True):
        location(post(client, f"/cases/{case_id}/vendors/{vendor.id}/reply", {"body": text}))
    rt.worker.run_pending()
    outreach = client.get(f"/cases/{case_id}?tab=outreach").text
    assert "Claude&#39;s read" in outreach or "Claude's read" in outreach

    location(post(client, f"/cases/{case_id}/compare"))
    rt.worker.run_pending()
    quotes = client.get(f"/cases/{case_id}?tab=quotes").text
    assert "Recommended" in quotes and "24\u00a0900\u00a0PLN" in quotes

    location(post(client, f"/cases/{case_id}/vendors/{contacted[0].id}/draft-reply", {"intent": "negotiate"}))
    rt.worker.run_pending()
    with rt.session() as db:
        reply = db.query(Message).filter(Message.vendor_id == contacted[0].id, Message.status == "draft").one()
        assert reply.subject.startswith("Re: ")

    choose = location(post(client, f"/cases/{case_id}/choose/{contacted[1].id}"))
    assert "chosen" in choose
    assert "You chose" in client.get(f"/cases/{case_id}?tab=quotes").text
    location(post(client, f"/cases/{case_id}/decision-emails"))
    rt.worker.run_pending()
    location(post(client, f"/cases/{case_id}/state", {"status": "closed"}))
    home = client.get("/?show=closed").text
    assert "Office chairs" in home

    activity = client.get(f"/cases/{case_id}?tab=activity").text
    assert "Brief confirmed" in activity and "failed" not in activity.split("Background steps")[1].split("</table>")[0]

    assert location(post(client, f"/cases/{case_id}/delete")) == "/"
    assert client.get(f"/cases/{case_id}").status_code == 404


def test_action_errors_are_shown_not_raised(client, rt):
    url = location(post(client, "/cases", {"request_text": "Need a painter for a 50 m2 flat in Kraków."}))
    case_id = int(re.search(r"/cases/(\d+)", url).group(1))
    response = post(client, f"/cases/{case_id}/vendors/search")
    assert "error=Confirm+the+brief" in location(response)
    page = client.get(location(response))
    assert "Confirm the brief first." in page.text
    assert "error=" in location(post(client, f"/cases/{case_id}/compare"))
