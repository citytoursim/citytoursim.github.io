#!/usr/bin/env python3
"""Update data/support.json with per-city support totals.

Reads Stripe with a restricted, read-only key (env STRIPE_RESTRICTED_KEY),
adds Bitcoin totals from data/support-btc.json, and writes only per-city
aggregates (amount and number of payments). It never prints the key and
never stores names, emails or any other supporter details.

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
            # Stripe error bodies never contain the key; print only the message.
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


def stripe_totals(key, currency, since_ts):
    """Return {slug: (amount_in_major_units, payment_count)} from Stripe."""
    totals = {}
    skipped_currency = 0
    for link in stripe_list(key, "payment_links", {}):
        slug = (link.get("metadata") or {}).get("city", "").strip()
        if not slug:
            continue
        params = {"payment_link": link["id"], "status": "complete", "created[gte]": since_ts}
        for session in stripe_list(key, "checkout/sessions", params):
            if session.get("payment_status") != "paid":
                continue
            if (session.get("currency") or "").lower() != currency:
                skipped_currency += 1
                continue
            amount, count = totals.get(slug, (0, 0))
            totals[slug] = (amount + (session.get("amount_total") or 0), count + 1)
    if skipped_currency:
        print(f"Skipped {skipped_currency} payment(s) in a currency other than {currency}.")
    # Stripe amounts are in the smallest unit (cents).
    return {slug: (cents / 100, count) for slug, (cents, count) in totals.items()}


def btc_totals():
    if not BTC.exists():
        return {}
    data = json.loads(BTC.read_text())
    out = {}
    for slug, row in (data.get("cities") or {}).items():
        out[slug] = (float(row.get("raised_usd") or 0), int(row.get("supporters") or 0))
    return out


def main():
    key = os.environ.get("STRIPE_RESTRICTED_KEY", "").strip()
    if not key:
        print("STRIPE_RESTRICTED_KEY is not set; nothing to update.")
        return 0

    data = json.loads(DATA.read_text())
    currency = (data.get("currency") or "usd").lower()
    start = data.get("round_start") or "1970-01-01"
    since_ts = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())

    card = stripe_totals(key, currency, since_ts)
    btc = btc_totals()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    changed = False
    for city in data["cities"]:
        slug = city["slug"]
        amount = card.get(slug, (0, 0))[0] + btc.get(slug, (0, 0))[0]
        count = card.get(slug, (0, 0))[1] + btc.get(slug, (0, 0))[1]
        amount = round(amount, 2)
        if amount != city.get("raised_usd") or count != city.get("supporters"):
            city["raised_usd"] = amount
            city["supporters"] = count
            city["updated"] = now
            changed = True

    if changed:
        data["updated"] = now
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print("Totals changed; data/support.json updated.")
    else:
        print("Totals unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
