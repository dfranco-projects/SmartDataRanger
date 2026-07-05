"""Concrete ingestors. Implemented by Unit 1 (Ingestors modernization).

Expected shape: TabularIngestor (parametrized by extension; covers csv/xlsx/parquet/
json/txt via the readers registry) and ZipIngestor (extracts into the workspace
extracted_dir with zip-slip protection, then ingests the members).
"""

from __future__ import annotations
