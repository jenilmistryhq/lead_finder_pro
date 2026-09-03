class LeadFinderError(Exception):
    """Base exception for all lead_finder errors."""


class ConfigError(LeadFinderError):
    """Raised when configuration is invalid or missing (bad flags, no API key)."""


class PlacesAPIError(LeadFinderError):
    """Raised when the Places API returns a non-retryable error, or all retries
    are exhausted on a retryable one."""
