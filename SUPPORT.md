# Support a city

The page at [/support/](https://citytoursim.com/support/) lets people support a planned city. Each payment counts as a
vote, and the city with the most support is the next one built. The page is `noindex` and is not linked from the home
page until payments open.

Card payments go through Stripe Payment Links and Bitcoin through a hosted checkout. Both open on the provider's own
page, so the site itself still has no forms, cookies or third-party scripts. A GitHub Action reads the totals from Stripe
every 30 minutes and commits only per-city aggregates.

## Checklist before opening (the user does these)

1. **Stripe account.** Open and verify a Stripe account for the project.
2. **One Payment Link per city.** In Stripe: Payment Links, New. Use a "customer chooses what to pay" price in USD,
   then under *Advanced* add metadata `city` = the city's slug from the table below. Without that metadata a
   payment is not counted. Turn on Apple Pay and Google Pay under Settings, Payment methods.
3. **Restricted read-only key.** In Stripe: Developers, API keys, Create restricted key. Give it **Read** on
   *Payment Links* and *Checkout Sessions*, and *None* on everything else.
4. **Repo secret.** In GitHub, open citytoursim/citytoursim.github.io, then Settings, Secrets and variables, Actions,
   New repository secret. Name it `STRIPE_RESTRICTED_KEY` and paste the key. Do this yourself: no Claude session should
   ever see the key, and it must never be committed.
5. **Bitcoin checkout.** Pick a hosted Bitcoin checkout provider (for example BTCPay Server, OpenNode or Coinbase
   Commerce), open the account, and create one checkout link per city.
6. **Paste the links** into `data/support.json`: `stripe_link` and `bitcoin_link` for each city (they must start with
   `https://`).
7. **Open the page.** Set `"open": true` in `data/support.json`, then add a link to /support/ in the home page nav and
   remove the `noindex` line from `support/index.html`.
8. **Run the Action once** from the Actions tab ("Support totals", Run workflow) to check that it works.

Buttons stay disabled with "Opens soon" while `open` is false or a city's link is empty.

## data/support.json

| Field | Meaning |
|---|---|
| `open` | `false` shows the "Opening soon" notice and disables every button. |
| `currency` | Currency counted from Stripe (`usd`). Payments in other currencies are skipped and logged. |
| `round_start` | ISO date. Only payments from this date (UTC) count. Move it to the 1st of a month to start a new round. |
| `updated` | When any total last changed (ISO timestamp, UTC), or `null`. Written by the Action. |
| `live` | Cities already in the game, listed on the page without buttons: `slug`, `name`, `country`. |
| `cities[]` | The cities people can vote for, in plan order (used to break ties). |
| `cities[].slug` | Matches the `city` metadata on that city's Stripe Payment Link. |
| `cities[].name`, `country` | Shown on the page. |
| `cities[].stripe_link` | Stripe Payment Link URL, or `""` until it exists. |
| `cities[].bitcoin_link` | Hosted Bitcoin checkout URL, or `""`. |
| `cities[].goal_usd` | The goal the progress bar fills toward. |
| `cities[].raised_usd` | Card plus Bitcoin total since `round_start`. Written by the Action. |
| `cities[].supporters` | Number of payments since `round_start` (not unique people). Written by the Action. |
| `cities[].updated` | When this city's total last changed, or `null`. Written by the Action. |

Edit everything except `raised_usd`, `supporters` and the `updated` fields by hand. The Action overwrites those.

## data/support-btc.json

Bitcoin totals, added on top of Stripe's. Update by hand (or later with a provider API step) in USD at the time of
payment:

```json
{ "cities": { "rome": { "raised_usd": 25, "supporters": 1 } } }
```

## The Action

`.github/workflows/support-totals.yml` runs every 30 minutes and on demand. It runs `scripts/support_totals.py`,
which:

- exits cleanly with a message if `STRIPE_RESTRICTED_KEY` is not set;
- lists every Payment Link, reads its `city` metadata, and sums the paid Checkout Sessions in `currency` since
  `round_start`;
- adds the Bitcoin totals, and writes `data/support.json` only if a number changed;
- never prints the key and never stores names, emails or other supporter details, only per-city amounts and counts.

GitHub pauses scheduled workflows after 60 days without repository activity. Run the workflow manually to resume it.

## City slugs

| City | Slug |
|---|---|
| Rome | `rome` |
| Barcelona | `barcelona` |
| Amsterdam | `amsterdam` |
| Dubai | `dubai` |
| Chicago | `chicago` |
| Las Vegas | `las-vegas` |
| Venice | `venice` |
| Los Angeles | `los-angeles` |
| Sydney | `sydney` |
| Istanbul | `istanbul` |
| Lisbon | `lisbon` |
| Prague | `prague` |
| Rio de Janeiro | `rio-de-janeiro` |
| Singapore | `singapore` |
| Berlin | `berlin` |
| Kyoto | `kyoto` |
| Washington, DC | `washington-dc` |
| Vienna | `vienna` |
| Hong Kong | `hong-kong` |
| Madrid | `madrid` |
| Mexico City | `mexico-city` |
| Cape Town | `cape-town` |
| Florence | `florence` |
| Budapest | `budapest` |
| Seattle | `seattle` |
| Edinburgh | `edinburgh` |
| Miami | `miami` |
| Toronto | `toronto` |
| Munich | `munich` |
| Buenos Aires | `buenos-aires` |
