"""Command-line entrypoint: parse args, wire the pipeline, report results."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

from .api_client import PlacesClient
from .cache import ResultsCache
from .config import Config, PLACES_TEXT_SEARCH_MAX, PROVIDERS
from .exceptions import LeadFinderError
from .exporters import export
from .osm_client import OverpassClient
from .scoring import details_to_lead

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lead_finder",
        description="Fetch and score public business leads — free via "
        "OpenStreetMap by default, or via the Google Places API.",
    )
    p.add_argument("--niche", required=True, help='Business type, e.g. "dentist"')
    p.add_argument("--city", required=True, help='e.g. "Austin, TX"')
    p.add_argument(
        "--provider", choices=PROVIDERS, default="osm",
        help="'osm' = free forever, no key (default). "
             "'google' = better data completeness, costs money past a small "
             "monthly free allowance, requires GOOGLE_PLACES_API_KEY.",
    )
    p.add_argument(
        "--osm-tag", default=None,
        help='Override the OSM tag used for --provider osm, e.g. "shop=bakery" '
             "(only needed if --niche isn't in the built-in list)",
    )
    p.add_argument(
        "--include-ratings", action="store_true",
        help="--provider google only: also fetch rating/review count. "
             "Bumps the call to Enterprise-tier pricing (1,000 free calls/month "
             "instead of 5,000) — off by default to keep costs down.",
    )
    p.add_argument(
        "--max-results", type=int, default=60,
        help=f"Hard cap is {PLACES_TEXT_SEARCH_MAX} per query (default: 60)",
    )
    p.add_argument(
        "--min-reviews-threshold", type=int, default=10,
        help="Below this review count counts as a 'weak' gap, Google only "
             "(default: 10)",
    )
    p.add_argument(
        "--min-score", type=int, default=0,
        help="Drop leads scoring below this (default: 0, keep all)",
    )
    p.add_argument(
        "--max-retries", type=int, default=4,
        help="Retry attempts per request on transient errors (default: 4)",
    )
    p.add_argument("--format", choices=["csv", "xlsx", "json"], default="csv")
    p.add_argument("--output", default=None, help="Output filename (default: auto-named)")
    p.add_argument("--cache-path", default=".lead_finder_cache.json")
    p.add_argument(
        "--no-cache", action="store_true",
        help="Disable the local per-query cache (forces a fresh fetch every run)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Search, fetch, and score, but skip writing an output file",
    )

    verbosity = p.add_mutually_exclusive_group()
    verbosity.add_argument("--verbose", action="store_true", help="Debug-level logging")
    verbosity.add_argument("--quiet", action="store_true", help="Warnings and errors only")

    return p


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def _fetch(cfg: Config) -> list:
    """Run the search against whichever provider is configured, using the
    cache when available. Returns a list of provider-neutral place dicts."""
    cache = ResultsCache(cfg.cache_path) if cfg.use_cache else None
    cache_key = f"{cfg.provider}:{cfg.niche}:{cfg.city}:{cfg.osm_tag or ''}".lower()

    cached = cache.get(cache_key) if cache else None
    if cached is not None:
        logger.info(
            "Using cached results for this exact query (%d places). Pass "
            "--no-cache or delete %s to force a fresh fetch.",
            len(cached), cfg.cache_path,
        )
        return cached

    if cfg.provider == "google":
        client = PlacesClient(
            api_key=cfg.api_key,
            max_retries=cfg.max_retries,
            include_ratings=cfg.include_ratings,
        )
        query = f"{cfg.niche} in {cfg.city}"
        logger.info("Searching (Google Places API): %r (max %d results)", query, cfg.max_results)
        raw_places = client.text_search(query, cfg.max_results)
    else:
        client = OverpassClient(max_retries=cfg.max_retries)
        logger.info(
            "Searching (OpenStreetMap, free): %r in %r (max %d results)",
            cfg.niche, cfg.city, cfg.max_results,
        )
        raw_places = client.text_search(cfg.niche, cfg.city, cfg.max_results, osm_tag=cfg.osm_tag)

    if cache is not None:
        cache.set(cache_key, raw_places)
        cache.save()

    return raw_places


def run(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = Config.from_args(args)
    except LeadFinderError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    configure_logging(cfg.log_level)

    try:
        raw_places = _fetch(cfg)
    except LeadFinderError as exc:
        logger.error("Search failed: %s", exc)
        return 1

    if not raw_places:
        logger.warning(
            "No results found. Try a broader niche, a nearby city, "
            "or (for --provider osm) a different --osm-tag."
        )
        return 0

    leads = [
        details_to_lead(p["place_id"], p, cfg.min_reviews_threshold) for p in raw_places
    ]
    leads = [l for l in leads if l.score >= cfg.min_score]
    leads.sort(key=lambda l: l.score, reverse=True)

    if not leads:
        logger.warning("No leads met --min-score threshold %d.", cfg.min_score)
        return 0

    logger.info("%d leads scored and sorted. Top 3:", len(leads))
    for lead in leads[:3]:
        logger.info("  %3d  %-35s  %s", lead.score, lead.name, lead.gap_notes)

    if cfg.dry_run:
        logger.info("--dry-run set: not writing an output file.")
        return 0

    output = cfg.output_path or (
        f"leads_{cfg.niche}_{cfg.city}".replace(" ", "_").replace(",", "")
        + f".{cfg.output_format}"
    )

    try:
        export(leads, cfg.output_format, output)
    except (ValueError, RuntimeError) as exc:
        logger.error("Export failed: %s", exc)
        return 1

    logger.info("Done. %d leads saved to %s", len(leads), output)
    logger.info(
        "Reminder: gbp_claimed / running_ads columns need the manual checks "
        "from Steps 3-4 of the masterclass before outreach."
    )
    return 0
