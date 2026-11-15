#!/usr/bin/env python3
"""Update data/support.json with all-time backers and amounts per city.

Every city button on /support/ opens the same Stripe Payment Link with
?client_reference_id=<slug>, so each paid Checkout Session says which city
it backs. A backer is one unique paying person per city (told apart in
memory by checkout email or customer id, never stored), so a single large
payment counts as one backer.

Reads Stripe with a restricted, read-only key (env STRIPE_RESTRICTED_KEY)
and adds Bitcoin numbers from data/support-btc.json. Writes only per-city
counts and amounts.

Exit codes: 0 when done or when the key is missing, 1 on a Stripe error.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "support.json"
BTC = ROOT / "data" / "support-btc.json"
API = "https://api.stripe.com/v1/"


def stripe_list(key, path, params):
    """Yield every object from a paginated Stripe list endpoint."""
    params = dict(params, limit=100)
    while True:
        url = API + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.load(resp)
        except urllib.error.HTTPError as err:
            try:
                msg = json.load(err).get("error", {}).get("message", "")
            except Exception:
                msg = ""
            sys.exit(f"Stripe returned HTTP {err.code} for {path}: {msg}")
        items = page.get("data", [])
        yield from items
        if not page.get("has_more") or not items:
            return
        params["starting_after"] = items[-1]["id"]


def session_city(session, link):
    """City from ?client_reference_id=, else the link's city metadata, else a 'city' dropdown."""
    ref = (session.get("client_reference_id") or "").strip()
    if ref:
        return ref
    meta = ((link.get("metadata") or {}).get("city") or "").strip()
    if meta:
        return meta
    for field in session.get("custom_fields") or []:
        if field.get("key") == "city":
            return ((field.get("dropdown") or {}).get("value") or "").strip()
    return ""


def supporter_id(session):
    """A per-run identity for de-duplicating backers. Never stored or printed."""
    email = ((session.get("customer_details") or {}).get("email") or "").strip().lower()
    return email or session.get("customer") or session["id"]


def stripe_totals(key, currency, known):
    cents, people = {}, {}
    skipped_currency = unknown = 0
    for link in stripe_list(key, "payment_links", {}):
        params = {"payment_link": link["id"], "status": "complete"}
        for session in stripe_list(key, "checkout/sessions", params):
            if session.get("payment_status") != "paid":
                continue
            if (session.get("currency") or "").lower() != currency:
                skipped_currency += 1
                continue
            slug = session_city(session, link)
            if slug not in known:
                unknown += 1
                continue
            cents[slug] = cents.get(slug, 0) + (session.get("amount_total") or 0)
            people.setdefault(slug, set()).add(supporter_id(session))
    if skipped_currency:
        print(f"Skipped {skipped_currency} payment(s) in a currency other than {currency}.")
    if unknown:
        print(f"Skipped {unknown} payment(s) without a known city.")
    return {slug: (cents[slug] / 100, len(people[slug])) for slug in cents}


def btc_totals():
    if not BTC.exists():
        return {}
    rows = (json.loads(BTC.read_text()).get("cities") or {})
    return {s: (float(r.get("raised_usd") or 0), int(r.get("backers") or 0)) for s, r in rows.items()}


def main():
    key = os.environ.get("STRIPE_RESTRICTED_KEY", "").strip()
    if not key:
        print("STRIPE_RESTRICTED_KEY is not set; nothing to update.")
        return 0

    data = json.loads(DATA.read_text())
    currency = (data.get("currency") or "usd").lower()
    known = {c["slug"] for c in data["cities"]}
    card = stripe_totals(key, currency, known)
    btc = btc_totals()
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    changed = False
    for city in data["cities"]:
        slug = city["slug"]
        raised = round(card.get(slug, (0, 0))[0] + btc.get(slug, (0, 0))[0], 2)
        backers = card.get(slug, (0, 0))[1] + btc.get(slug, (0, 0))[1]
        if raised != city.get("raised_usd") or backers != city.get("backers"):
            city["raised_usd"], city["backers"], city["updated"] = raised, backers, stamp
            changed = True

    if changed:
        data["updated"] = stamp
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print("Totals changed; data/support.json updated.")
    else:
        print("Totals unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
