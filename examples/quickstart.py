"""SmartDataRanger quickstart.

Creates a tiny example dataset under ``examples/data/`` (if the files are not
already there), imports it with :func:`smartdataranger.import_dataset`, and
walks through the resulting report.

Requires the full package to be implemented and installed (``uv sync``);
against the bare contract stubs this script raises ``NotImplementedError``.

Run from the repository root:

    uv run python examples/quickstart.py
"""

from __future__ import annotations

from pathlib import Path

from smartdataranger import import_dataset

DATA_DIR = Path(__file__).parent / "data"

SAMPLE_CSV = """\
name,park,since
Aria Stone,Yosemite,2015
Ben Okafor,Yellowstone,2018
Carmen Diaz,Zion,2012
Dev Patel,Acadia,2020
Elena Rossi,Denali,2016
"""

SAMPLE_JSON = """\
[
  {"name": "Frank Muller", "park": "Glacier", "since": 2014},
  {"name": "Grace Lin", "park": "Olympic", "since": 2019},
  {"name": "Hugo Mendes", "park": "Sequoia", "since": 2011},
  {"name": "Iris Novak", "park": "Badlands", "since": 2021},
  {"name": "Jack O'Neill", "park": "Arches", "since": 2017}
]
"""


def ensure_sample_data() -> None:
    """Create examples/data/ sample files if they do not exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in (("sample.csv", SAMPLE_CSV), ("sample.json", SAMPLE_JSON)):
        target = DATA_DIR / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")


def main() -> None:
    ensure_sample_data()

    frames, report = import_dataset(DATA_DIR)

    # A single data file yields a bare DataFrame; multiple files yield a dict.
    if not isinstance(frames, dict):
        frames = {report.files[0].metadata.file_name: frames}

    for file_name, df in frames.items():
        print(f"{file_name}: {df.shape[0]} rows x {df.shape[1]} columns")

    print(f"\nDiagnostics ({len(report.all_diagnostics)}):")
    for diag in report.all_diagnostics:
        location = diag.file or "<dataset>"
        print(f"  [{diag.severity}] {diag.code} ({location}): {diag.message}")

    for file_report in report.files:
        print(f"\nColumn profiles for {file_report.metadata.file_name}:")
        for profile in file_report.column_profiles:
            print(
                f"  {profile.name} ({profile.dtype}): "
                f"{profile.null_pct:.1f}% null, {profile.unique_count} unique"
            )

    if report.has_errors():
        print("\nImport finished with errors — see diagnostics above.")


if __name__ == "__main__":
    main()
