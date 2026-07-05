"""SmartDataRanger: reliable, reproducible, fully-offline dataset onboarding.

This module is FINAL: work units must not edit it.
"""

from .api import import_dataset
from .loader import load_dataset
from .models import (
    ColumnProfile,
    Diagnostic,
    FileMetadata,
    FileReport,
    ImportReport,
    Severity,
)

__version__ = "0.2.0"

__all__ = [
    "ColumnProfile",
    "Diagnostic",
    "FileMetadata",
    "FileReport",
    "ImportReport",
    "Severity",
    "__version__",
    "import_dataset",
    "load_dataset",
]
