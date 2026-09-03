"""A local JSON cache keyed by search query, so re-running the exact same
niche+city (+ provider) doesn't re-hit a paid API or a shared public
service you're trying to be polite to."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ResultsCache:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._data: Dict[str, list] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
                logger.debug(
                    "Loaded %d cached queries from %s", len(self._data), self.path
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not read cache at %s (%s) — starting fresh", self.path, exc
                )

    def get(self, key: str) -> Optional[list]:
        return self._data.get(key)

    def set(self, key: str, results: list) -> None:
        self._data[key] = results

    def save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._data, indent=2))
        except OSError as exc:
            logger.warning("Could not write cache to %s: %s", self.path, exc)
