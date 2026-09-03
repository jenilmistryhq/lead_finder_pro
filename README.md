# Lead Finder

Fetch and score public local-business leads for SEO/Google-Ads outreach —
**free forever via OpenStreetMap by default**, with an optional Google
Places API backend for more complete data.

Each business gets scored on real gap signals — no website, thin reviews,
low rating, non-operational status — then gets exported to a sorted
CSV, XLSX, or JSON you can drop straight into outreach.

## Why this exists

Most "find local business leads" scripts either scrape Google Maps
directly (breaks Google's Terms of Service, gets IPs blocked) or assume
an API budget you may not have. This tool defaults to a genuinely free
data source, is explicit about what the paid alternative actually costs,
and scores leads consistently across both.

## Two data sources

Pick with `--provider`:

| | `osm` (default) | `google` |
|---|---|---|
| Cost | **$0, forever** | Free monthly allowance, then billed |
| Signup | None | Google Cloud project + billing + API key |
| Card required | No | **Yes**, even to stay within the free tier |
| Data completeness | Variable — crowdsourced, phone/website often missing | Much more complete; ratings/reviews available |
| Rate limit | Be polite to shared public infra (~1 req/sec) | Governed by your Google Cloud quota |

### Is the Google option really "free forever"? Read this first.

**No** — not with zero investment. Google's pricing model changed in 2025
in a way that's easy to get wrong:

- It's **not** "free for a month, then you must pay." The free monthly
  allowance **resets every month, forever** — it doesn't expire.
- But it's **not free with zero investment either** — Google requires
  **billing enabled and a card on file** before you can call the API at
  all, free tier or not.
- The old flat $200/month credit was **retired in March 2025**, replaced
  by **per-field-tier monthly allowances**: roughly 10,000 free
  calls/month for basic fields, 5,000/month once you add contact fields
  (phone, website), and only **1,000/month** if you add rating/review
  data — Google prices a whole response at the tier of its priciest
  requested field.
- This tool's Google mode **excludes rating/review fields by default**
  to stay in the larger 5,000/month bracket. Pass `--include-ratings` if
  you want that data anyway — it costs more.
- Also worth knowing: the **old "Places API (Legacy)" endpoints can no
  longer be enabled on a new Google Cloud project at all** (frozen since
  March 2025). This tool targets the current **Places API (New)**.

**If "zero investment, free forever" is a hard requirement, use
`--provider osm`** (the default) — genuinely free, no card, ever.

## Installation

```bash
pip install lead-finder
```

With Excel export and `.env` file support:
```bash
pip install "lead-finder[xlsx,dotenv]"
```

<details>
<summary>Installing from source instead</summary>

```bash
git clone https://github.com/jenilmistryhq/lead-finder.git
cd lead-finder
pip install -e ".[xlsx,dotenv]"
```
</details>

No further setup is needed for the default `osm` provider — no key, no
signup, no card.

For `--provider google`, additionally:
1. https://console.cloud.google.com → new project (free)
2. Enable **Places API (New)**, enable billing (card required)
3. Create an API key, restrict it to "Places API (New)"
4. `export GOOGLE_PLACES_API_KEY="your-key"` (or use a `.env` file — see `.env.example`)

## Quickstart

Free, no key, no card — the default:
```bash
lead-finder --niche "dentist" --city "Austin, TX"
```

If your niche isn't in the built-in OSM tag list, point it at the right tag
(browse tags at https://wiki.openstreetmap.org/wiki/Map_features):
```bash
lead-finder --niche "notary" --city "Austin, TX" --osm-tag "office=notary"
```

Google, more complete data, costs money past the free allowance:
```bash
lead-finder --niche "dentist" --city "Austin, TX" --provider google
lead-finder --niche "dentist" --city "Austin, TX" --provider google --include-ratings
```

Output is a sorted CSV/XLSX/JSON named like `leads_dentist_Austin_TX.csv`
in your working directory, highest-scored (biggest gap) lead first.

## Options

| Flag | Default | What it does |
|---|---|---|
| `--niche` | *required* | Business type, e.g. `"dentist"` |
| `--city` | *required* | e.g. `"Austin, TX"` |
| `--provider` | `osm` | `osm` (free) or `google` (paid past free allowance) |
| `--osm-tag` | auto | Override the OSM tag for `--provider osm` |
| `--include-ratings` | off | `--provider google` only — adds rating data, costs more |
| `--max-results` | 60 | Hard cap per query |
| `--min-reviews-threshold` | 10 | Below this = flagged as a review gap (Google only) |
| `--min-score` | 0 | Drop leads scoring below this |
| `--max-retries` | 4 | Retry attempts on transient errors |
| `--format` | csv | `csv`, `xlsx`, or `json` |
| `--output` | auto-named | Output file path |
| `--cache-path` | `.lead_finder_cache.json` | Local per-query cache location |
| `--no-cache` | off | Force a fresh fetch, skip the cache |
| `--dry-run` | off | Search/score but skip writing a file |
| `--verbose` / `--quiet` | normal | Debug logging / warnings-only |

Also runnable without installing the console script:
```bash
python -m lead_finder --niche "dentist" --city "Austin, TX"
```

## What neither provider can do

- **GBP-claimed status** and **running-ads status** aren't exposed by
  either API — those columns come back as `CHECK MANUALLY`. These need a
  quick manual check per lead (a Google Business Profile glance and a
  Meta Ad Library search) before outreach.
- **OSM has no rating/review data at all.** `rating`/`reviews` come back
  empty for every OSM lead, with a note explaining why — not a false
  "0 reviews."
- **60 results per query is a hard cap** for both providers — narrow by
  neighborhood and run multiple queries to cover more ground.

## Long-term data storage (Google provider only)

Google's Places API terms include specific rules on caching/storing
results if you're building a persistent database rather than doing
one-off exports. The local cache here just avoids re-billing identical
searches within a session — it isn't a permanent data store. If you plan
to sync this into a CRM you keep updating over months, check current
terms: https://cloud.google.com/maps-platform/terms

## Development

```bash
git clone https://github.com/jenilmistryhq/lead-finder.git
cd lead-finder
pip install -e ".[dev,xlsx,dotenv]"
pytest -v
```

30 tests, all against mocked HTTP responses — no API key, no network, and
no cost to run them.

### Project layout

```
lead_finder/
├── __init__.py
├── __main__.py       # enables `python -m lead_finder`
├── cli.py             # argument parsing + pipeline orchestration
├── config.py           # env/.env/CLI resolution + validation
├── api_client.py        # Google Places API (New) client
├── osm_client.py         # free OpenStreetMap / Overpass client
├── cache.py                # local per-query JSON cache
├── scoring.py                # Lead dataclass + gap-scoring model
├── exporters.py                # CSV / XLSX / JSON export
tests/
├── test_scoring.py
├── test_exporters.py
├── test_api_client.py
├── test_osm_client.py
```

### Contributing

Issues and PRs welcome. If you're adding a new OSM niche mapping, add it
to `NICHE_TAG_MAP` in `osm_client.py` plus a one-line test in
`test_osm_client.py`. Run `pytest -v` before opening a PR.

## Legal note

This tool only queries data sources' own official, public APIs (OpenStreetMap's Nominatim/Overpass, Google's Places API) — it does not scrape web pages or bypass authentication, CAPTCHAs, or rate limits. You're responsible for using the output in line with each source's terms of service and applicable anti-spam/privacy law in your outreach.

## License

[MIT](LICENSE)
