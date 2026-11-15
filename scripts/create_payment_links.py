#!/usr/bin/env python3
"""Create one Stripe Payment Link per city and write the URLs into data/support.json.

Run this LOCALLY with your own key in an environment variable. Never commit
the key and never paste it into a chat:

    export STRIPE_SECRET_KEY=sk_test_...   # test mode first, then sk_live_...
    python3 scripts/create_payment_links.py --dry-run
    python3 scripts/create_payment_links.py

Each link is "pay what you want" in the page currency, with metadata
city=<slug> on the link and on the payment, so the totals workflow can
count it. Idempotent: cities that already have a stripe_link in
data/support.json are skipped, and links that already exist in Stripe with
the same city metadata are reused instead of created twice.

Options: --dry-run (show what would happen), --only rome,venice (limit to
these slugs), --min 1 --preset 5 (amounts in whole currency units).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "support.json"
API = "https://api.stripe.com/v1/"
RETURN_URL = "https://citytoursim.com/support/?thanks=1"


def call(key, method, path, params=None, idem=None):
    body = urllib.parse.urlencode(params or {}).encode() if method == "POST" else None
    url = API + path + ("?" + urllib.parse.urlencode(params) if method == "GET" and params else "")
    headers = {"Authorization": "Bearer " + key}
    if idem:
        headers["Idempotency-Key"] = idem
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        try:
            msg = json.load(err).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        sys.exit(f"Stripe returned HTTP {err.code} for {path}: {msg}")


def existing_links(key):
    """Map city slug -> URL for active Payment Links that already carry city metadata."""
    found, params = {}, {"limit": 100, "active": "true"}
    while True:
        page = call(key, "GET", "payment_links", params)
        for link in page.get("data", []):
            slug = (link.get("metadata") or {}).get("city")
            if slug and slug not in found:
                found[slug] = link["url"]
        if not page.get("has_more") or not page.get("data"):
            return found
        params["starting_after"] = page["data"][-1]["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--min", type=int, default=1)
    ap.add_argument("--preset", type=int, default=5)
    args = ap.parse_args()

    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        sys.exit("Set STRIPE_SECRET_KEY in your shell first (see the top of this file).")
    mode = "test" if key.startswith(("sk_test_", "rk_test_")) else "LIVE"

    data = json.loads(DATA.read_text())
    currency = (data.get("currency") or "usd").lower()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    cities = [c for c in data["cities"] if not only or c["slug"] in only]

    in_stripe = existing_links(key)
    created, reused, skipped = [], [], []
    for city in cities:
        slug = city["slug"]
        if city.get("stripe_link"):
            skipped.append(slug)
            continue
        if slug in in_stripe:
            city["stripe_link"] = in_stripe[slug]
            reused.append(slug)
            continue
        if args.dry_run:
            created.append(slug)
            continue
        price = call(key, "POST", "prices", {
            "currency": currency,
            "custom_unit_amount[enabled]": "true",
            "custom_unit_amount[minimum]": args.min * 100,
            "custom_unit_amount[preset]": args.preset * 100,
            "product_data[name]": f"Support City Tour Simulator: vote for {city['name']}",
            "metadata[city]": slug,
        }, idem=f"cts-price-{slug}-{mode}")
        link = call(key, "POST", "payment_links", {
            "line_items[0][price]": price["id"],
            "line_items[0][quantity]": 1,
            "metadata[city]": slug,
            "payment_intent_data[metadata][city]": slug,
            "after_completion[type]": "redirect",
            "after_completion[redirect][url]": RETURN_URL,
        }, idem=f"cts-link-{slug}-{mode}")
        city["stripe_link"] = link["url"]
        created.append(slug)

    if not args.dry_run and (created or reused):
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    verb = "Would create" if args.dry_run else "Created"
    print(f"Stripe {mode} mode.")
    print(f"{verb}: {len(created)} {', '.join(created)}")
    print(f"Reused existing links: {len(reused)} {', '.join(reused)}")
    print(f"Skipped (already had a link): {len(skipped)}")
    if not args.dry_run and (created or reused):
        print("data/support.json updated. Review the diff, then commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
