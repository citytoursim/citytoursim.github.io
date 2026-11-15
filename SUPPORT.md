# Back a city

[/support/](https://citytoursim.com/support/) lets anyone back a city at any time: an upcoming city (the most-backed
one is built next) or a city already in the game (support goes toward improving it). It is public and linked from the
home page, and shows **Opening soon** with every button reading "Soon" until payments are set up.

- **Backers, not dollars:** each city shows how many unique people have backed it, all time. Upcoming cities are ranked
  by backers, so one large payment counts as one backer. Amounts are tracked in the data file but not shown.
- **One payment link:** every "Back" button opens the same Stripe Payment Link with `?client_reference_id=<slug>`
  added, so Stripe records which city each payment backs. The supporter doesn't have to choose the city again.
- **No forms, cookies or third-party scripts** on the site: checkout happens on Stripe's page.
- **Wording:** "back" or "support the project", never "donation", never anything that reads as buying a city or map
  content. The footnote on the page says it's voluntary support, not a purchase or a guarantee; payments are handled
  by Stripe; refunds as the law requires; counts shown, never names.

## Setup checklist (the user does these)

1. **Stripe account:** open and verify it, and turn on Apple Pay and Google Pay (Settings, Payment methods).
2. **One Payment Link:** Payment Links, New, with a "customer chooses what to pay" price in USD (for example a $5
   suggestion and a $1 minimum). Under *After payment*, redirect to `https://citytoursim.com/support/?thanks=1`.
3. **Read-only key:** Developers, API keys, Create restricted key, with **Read** on *Payment Links* and *Checkout
   Sessions* and *None* on everything else.
4. **Repo secret:** in GitHub, citytoursim/citytoursim.github.io, Settings, Secrets and variables, Actions, New
   repository secret, named `STRIPE_RESTRICTED_KEY`. Do this yourself: no Claude session should ever see a key, and
   keys never go in the repo.
5. **Open it:** in `data/support.json`, paste the link as `stripe_link` and set `"open": true`. Optionally add a
   hosted Bitcoin checkout link as `bitcoin_link`; the page then shows a small "Back with Bitcoin" link.
6. **Check:** run "Support totals" once from the repo's Actions tab, then make a small test payment.

## data/support.json

| Field | Meaning |
|---|---|
| `open` | `false` shows "Opening soon" and disables every button. |
| `currency` | Currency counted from Stripe (`usd`); other currencies are skipped and logged. |
| `stripe_link` | The single Stripe Payment Link (`https://buy.stripe.com/...`). |
| `bitcoin_link` | Optional hosted Bitcoin checkout link. |
| `updated` | When any number last changed (UTC), or `null`. Written by the Action. |
| `cities[].slug` | Sent to Stripe as `client_reference_id` (lowercase letters, digits and hyphens only). |
| `cities[].name`, `country` | Shown on the page. |
| `cities[].status` | `upcoming` (ranked under "Next up") or `live` (shown as a card under "In the game"). |
| `cities[].thumb` | Image for live cities. |
| `cities[].backers` | Unique paying backers, all time. Written by the Action. |
| `cities[].raised_usd` | Total amount, all time. Written by the Action, not shown on the page. |
| `cities[].updated` | When this city's numbers last changed. Written by the Action. |

When a city launches, change its `status` from `upcoming` to `live` and add a `thumb`. Its backers carry over.
To add a city, add a row with a new slug.

`data/support-btc.json` holds Bitcoin numbers per city (`backers`, `raised_usd`), updated by hand and added to the
Stripe numbers. Someone who backs by card and by Bitcoin counts twice.

## The Action

`.github/workflows/support-totals.yml` runs every 30 minutes and on demand. `scripts/support_totals.py`:

- exits cleanly with a message if `STRIPE_RESTRICTED_KEY` is missing;
- reads every paid Checkout Session from the Payment Links and takes the city from `client_reference_id`, or from the
  link's `city` metadata, or from a `city` dropdown field;
- counts unique backers per city (told apart in memory by checkout email or customer id, never stored) and sums the
  amounts;
- writes `data/support.json` and commits only when a number changes;
- never prints a key or stores names, emails or other personal details.

GitHub pauses scheduled workflows after 60 days without repository activity. Run it manually to restart it.
