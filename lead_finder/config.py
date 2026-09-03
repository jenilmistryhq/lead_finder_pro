"""Central configuration: resolves env vars, an optional .env file, and CLI
flags into one validated, immutable Config object."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()  # no-op if no .env file is present
except ImportError:
    pass  # python-dotenv is optional; plain env vars still work

from .exceptions import ConfigError

PLACES_TEXT_SEARCH_MAX = 60  # Google's own hard cap per Text Search query
PROVIDERS = ("osm", "google")


@dataclass(frozen=True)
class Config:
    provider: str = "osm"
    api_key: Optional[str] = None
    niche: str = ""
    city: str = ""
    osm_tag: Optional[str] = None
    include_ratings: bool = False
    max_results: int = 60
    min_reviews_threshold: int = 10
    min_score: int = 0
    max_retries: int = 4
    output_format: str = "csv"
    output_path: Optional[str] = None
    cache_path: str = ".lead_finder_cache.json"
    use_cache: bool = True
    dry_run: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_args(cls, args) -> "Config":
        provider = args.provider
        if provider not in PROVIDERS:
            raise ConfigError(f"--provider must be one of {PROVIDERS}.")

        api_key = None
        if provider == "google":
            api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
            if not api_key:
                raise ConfigError(
                    "GOOGLE_PLACES_API_KEY is not set (required for "
                    "--provider google). Export it, add it to a .env file, "
                    "or drop --provider to use the free OSM source instead."
                )

        if not args.niche.strip():
            raise ConfigError("--niche cannot be empty.")
        if not args.city.strip():
            raise ConfigError("--city cannot be empty.")
        if args.max_results < 1 or args.max_results > PLACES_TEXT_SEARCH_MAX:
            raise ConfigError(
                f"--max-results must be between 1 and {PLACES_TEXT_SEARCH_MAX}."
            )
        if args.min_score < 0:
            raise ConfigError("--min-score cannot be negative.")

        log_level = "DEBUG" if args.verbose else ("WARNING" if args.quiet else "INFO")

        return cls(
            provider=provider,
            api_key=api_key,
            niche=args.niche.strip(),
            city=args.city.strip(),
            osm_tag=args.osm_tag,
            include_ratings=args.include_ratings,
            max_results=args.max_results,
            min_reviews_threshold=args.min_reviews_threshold,
            min_score=args.min_score,
            max_retries=args.max_retries,
            output_format=args.format,
            output_path=args.output,
            cache_path=args.cache_path,
            use_cache=not args.no_cache,
            dry_run=args.dry_run,
            log_level=log_level,
        )
