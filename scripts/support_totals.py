#!/usr/bin/env python3
"""Update data/support.json with this month's per-city votes and funding.

A vote is one unique paying supporter per city per calendar month (UTC),
so one large payment cannot decide the result alone. Dollars are shown
separately as funding progress.

Reads Stripe with a restricted, read-only key (env STRIPE_RESTRICTED_KEY)
and adds Bitcoin totals from data/support-btc.json. Supporters are told
apart in memory only (by checkout email or customer id) and are never
written anywhere: the output is per-city counts and amounts.

Exit codes: 0 when done or when the key is missing (nothing to do),
1 when Stripe returns an error.
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
CITY_FIELD = "city"  # metadata key on Payment Links, or custom-field key on a single link


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


def session_city(session, link_city):
    """City from the Payment Link metadata, or from a 'city' dropdown on a single shared link."""
    if link_city:
        return link_city
    for field in session.get("custom_fields") or []:
        if field.get("key") == CITY_FIELD:
            return ((field.get("dropdown") or {}).get("value") or "").strip()
    return ""


def supporter_id(session):
    """A per-run identity for de-duplicating supporters. Never stored or printed."""
    details = session.get("customer_details") or {}
    email = (details.get("email") or "").strip().lower()
    return email or session.get("customer") or session["id"]


def stripe_totals(key, currency, since_ts, known):
    """Return {slug: (amount_in_major_units, unique_supporters)} for paid sessions."""
    cents = {}
    people = {}
    skipped_currency = unknown = 0
    for link in stripe_list(key, "payment_links", {}):
        link_city = ((link.get("metadata") or {}).get(CITY_FIELD) or "").strip()
        params = {"payment_link": link["id"], "status": "complete", "created[gte]": since_ts}
        for session in stripe_list(key, "checkout/sessions", params):
            if session.get("payment_status") != "paid":
                continue
            if (session.get("currency") or "").lower() != currency:
                skipped_currency += 1
                continue
            slug = session_city(session, link_city)
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


def btc_totals(month):
    if not BTC.exists():
        return {}
    data = json.loads(BTC.read_text())
    if data.get("month") != month:
        return {}
    out = {}
    for slug, row in (data.get("cities") or {}).items():
        out[slug] = (float(row.get("raised_usd") or 0), int(row.get("votes") or 0))
    return out


def main():
    key = os.environ.get("STRIPE_RESTRICTED_KEY", "").strip()
    if not key:
        print("STRIPE_RESTRICTED_KEY is not set; nothing to update.")
        return 0

    data = json.loads(DATA.read_text())
    currency = (data.get("currency") or "usd").lower()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    month = month_start.strftime("%Y-%m")
    stamp = now.isoformat().replace("+00:00", "Z")

    known = {c["slug"] for c in data["cities"]}
    card = stripe_totals(key, currency, int(month_start.timestamp()), known)
    btc = btc_totals(month)

    changed = False
    rnd = data.setdefault("round", {})
    if rnd.get("month") != month:
        rnd["month"] = month
        changed = True
    for city in data["cities"]:
        slug = city["slug"]
        raised = round(card.get(slug, (0, 0))[0] + btc.get(slug, (0, 0))[0], 2)
        votes = card.get(slug, (0, 0))[1] + btc.get(slug, (0, 0))[1]
        if raised != city.get("raised_usd") or votes != city.get("votes"):
            city["raised_usd"] = raised
            city["votes"] = votes
            city["updated"] = stamp
            changed = True

    if changed:
        data["updated"] = stamp
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"Totals for {month} changed; data/support.json updated.")
    else:
        print(f"Totals for {month} unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
