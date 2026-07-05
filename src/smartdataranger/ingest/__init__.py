"""Ingestion subpackage. This module is FINAL: work units must not edit it."""

from .base import Ingestor
from .factory import get_ingestor, ingest_directory

__all__ = ["Ingestor", "get_ingestor", "ingest_directory"]
