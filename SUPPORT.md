# Support a city

[/support/](https://citytoursim.com/support/) is a monthly vote on which planned city is built next. It is public and
linked from the home page, and shows **Opening soon** with every button disabled until payments are set up.

- **One supporter, one vote:** each unique paying supporter counts once per city per calendar month (UTC), however
  much they give. Cities that are not in the game yet are ranked by votes, high to low, with the amount raised shown
  next to them. There are no funding goals.
- **The winner** is the city with the most votes when the month's vote closes, after a check that its 3D coverage and
  quality are good enough. A city can be skipped or delayed for coverage, quality or legal reasons. A city takes 6 to 8
  weeks to make, so each vote decides the release about two months later.
- **Wording:** "support the project", never "donation", and never anything that reads as buying a city or map content.
  The page's Terms block says it is voluntary support, not a purchase; a vote, not a guarantee; refunds as the law
  requires; public totals, never names; payments processed by Stripe and the Bitcoin checkout provider.

Card payments use Stripe Payment Links and Bitcoin uses a hosted checkout. Both open on the provider's own page, so the
site still has no forms, cookies or third-party scripts. A GitHub Action reads the totals from Stripe every 30 minutes
and commits only per-city aggregates.

## Checklist before opening (the user does these)

1. **Stripe account.** Open and verify a Stripe account for the project. Turn on Apple Pay and Google Pay under
   Settings, Payment methods.
2. **Payment Links, one per city.** Easiest is the script below, which creates all 30. To do it by hand: Payment
   Links, New, a "customer chooses what to pay" price in USD, and under *Advanced* add metadata `city` = the slug from
   the table at the end. Without that metadata a payment is not counted.
3. **Restricted read-only key for the Action.** In Stripe: Developers, API keys, Create restricted key. Give it
   **Read** on *Payment Links* and *Checkout Sessions*, and *None* on everything else.
4. **Repo secret.** In GitHub, open citytoursim/citytoursim.github.io, then Settings, Secrets and variables, Actions,
   New repository secret. Name it `STRIPE_RESTRICTED_KEY` and paste the restricted key. Do this yourself: no Claude
   session should ever see a key, and keys must never be committed.
5. **Bitcoin checkout.** Pick a hosted provider (for example BTCPay Server, OpenNode or Coinbase Commerce), open the
   account, create one checkout link per city, and paste them as `bitcoin_link` in `data/support.json`.
6. **Vote dates.** Fill in `round.vote_closes` and `round.decides_release` in `data/support.json`.
7. **Open payments.** Set `"open": true` in `data/support.json` and commit.
8. **Run the Action once** from the Actions tab ("Support totals", Run workflow) to check that it works.

Buttons stay disabled ("Card opens soon", "Bitcoin opens soon") while `open` is false or a city's link is empty.

## Creating the Payment Links with a script

`scripts/create_payment_links.py` creates one "pay what you want" Payment Link per city, sets metadata `city=<slug>`
on the link and on the payment, and writes the URLs into `data/support.json`. Run it locally on your own computer,
with a key you set in your own shell. Never commit the key and never paste it into a chat. The key needs write access
to Products, Prices and Payment Links, so a standard secret key or a restricted key with those permissions.

```bash
export STRIPE_SECRET_KEY=sk_test_...       # test mode first
python3 scripts/create_payment_links.py --dry-run
python3 scripts/create_payment_links.py    # then commit data/support.json
```

- **Idempotent:** cities that already have a `stripe_link` are skipped, and links that already exist in Stripe with the
  same `city` metadata are reused, not created twice.
- **Options:** `--only rome,venice`, `--min 1` (minimum amount, default 1), `--preset 5` (suggested amount,
  default 5).
- **Redirect:** after paying, supporters return to `/support/?thanks=1`, which shows a thank-you line.
- **Test and live:** test-mode links work only with test cards. When you switch to live mode, empty the
  `stripe_link` values and run it again with the live key.

### Alternative: one link with a "Which city?" dropdown

Instead of 30 links, create a single Payment Link with a custom field of type *Dropdown*, key `city`, and one option
per city whose value is the slug. Paste the same URL as `stripe_link` for every city. Leave the link's metadata empty.
The Action already handles this: when a Payment Link has no `city` metadata, it reads the `city` dropdown value from
each Checkout Session (`custom_fields[].dropdown.value`). The trade-off: supporters have to pick the city again on
Stripe's page, and the button on the page cannot preselect it.

## data/support.json

| Field | Meaning |
|---|---|
| `open` | `false` shows the "Opening soon" notice and disables every button. |
| `currency` | Currency counted from Stripe (`usd`). Payments in other currencies are skipped and logged. |
| `show_live` | `true` lists the cities already in the game below the vote (no buttons). `false` hides that list. |
| `round.month` | The month being counted (`YYYY-MM`). Written by the Action. |
| `round.vote_closes` | ISO date the vote closes, shown on the page. `null` shows "Vote dates will be announced". |
| `round.decides_release` | Text such as `"February 2027"`, shown as "decides the February 2027 release". |
| `updated` | When any total last changed (ISO timestamp, UTC), or `null`. Written by the Action. |
| `live[]` | Cities already in the game: `slug`, `name`, `country`. |
| `cities[]` | The cities people can vote for, in plan order (used to break ties). Add or remove cities here. |
| `cities[].slug` | Matches the `city` metadata (or dropdown value) in Stripe. |
| `cities[].name`, `country` | Shown on the page. |
| `cities[].stripe_link` | Stripe Payment Link URL, or `""`. Must start with `https://`. |
| `cities[].bitcoin_link` | Hosted Bitcoin checkout URL, or `""`. |
| `cities[].votes` | Unique paying supporters this month (card plus Bitcoin). Written by the Action. Decides the ranking; the bar shows votes relative to the leading city. |
| `cities[].raised_usd` | Amount this month, card plus Bitcoin. Written by the Action. |
| `cities[].updated` | When this city's numbers last changed, or `null`. Written by the Action. |

Edit everything by hand except `round.month`, `votes`, `raised_usd` and the `updated` fields; the Action
overwrites those.

## data/support-btc.json

Bitcoin numbers for the current month, added on top of Stripe's. Update by hand (or later with a provider API step).
They're used only when `month` matches the current month:

```json
{ "month": "2026-12", "cities": { "rome": { "votes": 1, "raised_usd": 25 } } }
```

A person who supports by card and by Bitcoin counts twice, because the two providers can't be matched without storing
personal data.

## The Action

`.github/workflows/support-totals.yml` runs every 30 minutes and on demand. It runs `scripts/support_totals.py`,
which:

- exits cleanly with a message if `STRIPE_RESTRICTED_KEY` is not set;
- lists every Payment Link and reads its `city` metadata, or the session's `city` dropdown;
- takes the paid Checkout Sessions in `currency` since the 1st of the current month (UTC), so totals reset each month;
- counts votes as unique supporters per city, told apart in memory only by checkout email or customer id, and sums the
  amounts;
- adds the Bitcoin numbers and writes `data/support.json` only if something changed;
- never prints a key and never stores names, emails or other supporter details: only per-city counts and amounts.

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
