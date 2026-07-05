# SmartDataRanger

Point it at a folder of messy data files; get clean pandas DataFrames, deterministic
diagnostics, per-column quality profiles, and a reproducible `metadata.json` —
100% offline, no API keys, no LLMs.

Every import step is plain, deterministic Python: encoding detection via
charset-normalizer, delimiter sniffing via the stdlib `csv.Sniffer`, and a
whitelisted reader registry instead of dynamic code execution. The same input
always produces the same output.

## Supported formats

| Extension       | Reader                | Notes                           |
| --------------- | --------------------- | ------------------------------- |
| `.csv`          | `pandas.read_csv`     | encoding + delimiter detection  |
| `.txt`          | `pandas.read_csv`     | tab-separated by default        |
| `.xlsx`, `.xls` | `pandas.read_excel`   | via openpyxl                    |
| `.parquet`      | `pandas.read_parquet` | via pyarrow                     |
| `.json`         | `pandas.read_json`    |                                 |
| `.zip`          | archive extraction    | members ingested individually   |

Anything else is skipped with an `UNSUPPORTED_FILE_SKIPPED` diagnostic — never a crash.

## Install

```sh
pip install smartdataranger
# or
uv add smartdataranger
```

> Not yet on PyPI. For now, install from source:
>
> ```sh
> git clone https://github.com/dfranco-projects/SmartDataRanger
> cd SmartDataRanger
> uv sync
> ```

Requires Python 3.13+.

## Quickstart

```python
from smartdataranger import import_dataset

frames, report = import_dataset("path/to/data")

for diag in report.all_diagnostics:
    print(diag.severity, diag.code, diag.message)
```

`import_dataset` ingests a folder (or a single file), loads DataFrames, runs
diagnostics and per-column profiling, and writes a reproducible
`metadata.json`. A single data file yields a bare `DataFrame`; multiple files
yield a `{file_name: DataFrame}` dict; an empty folder yields `({}, report)`
with a dataset-level `EMPTY_DATASET` diagnostic.

```python
def import_dataset(
    path: str | Path,
    *,
    profile: bool = True,
    write_metadata: bool = True,
) -> tuple[pd.DataFrame | dict[str, pd.DataFrame], ImportReport]: ...
```

A runnable version lives in [`examples/quickstart.py`](examples/quickstart.py).

## CLI

```sh
ranger scan path/to/data              # rich terminal report
ranger scan path/to/data --json       # machine-readable report
ranger scan path/to/data --no-profile --no-write-metadata
```

`ranger scan` runs `import_dataset` and renders the report. It exits with
status 1 if the report contains any error-severity diagnostics — handy in
pipelines and pre-commit checks.

Sample output (abridged — one profile table is rendered per file):

```text
$ ranger scan ./demo
╭──────────────────── Scan summary ────────────────────╮
│ Root: /path/to/demo                                   │
│ Files ingested: 4                                     │
│ Total rows: 13                                        │
│ Errors: 0  Warnings: 2  Info: 5                       │
╰───────────────────────────────────────────────────────╯
                        people.csv
┏━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Column ┃ Dtype   ┃ Nulls % ┃ Unique ┃ Samples          ┃
┡━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ id     │ int64   │     0.0 │      3 │ 1, 2, 3          │
│ name   │ str     │     0.0 │      3 │ ada, grace, alan │
│ score  │ float64 │    25.0 │      2 │ 9.5, 7.0         │
└────────┴─────────┴─────────┴────────┴──────────────────┘
Diagnostics
WARNING ENCODING_NON_UTF8 messy.csv — File is not UTF-8 encoded (detected cp1250).
INFO DELIMITER_SNIFFED messy.csv — Detected non-comma delimiter ';'.
WARNING MALFORMED_ROWS messy.csv — 1 row(s) have a field count different from the header (3 fields expected).
INFO UNSUPPORTED_FILE_SKIPPED notes.docx — Unsupported file type '.docx'; skipped.
INFO DUPLICATE_ROWS people.csv — people.csv has 1 fully duplicated row(s)
```

## Diagnostics reference

Each finding is a `Diagnostic` with a stable `code`, a `Severity`
(`info` / `warning` / `error`), a human-readable `message`, and the file
(and optionally column) it applies to.

| Code                       | Severity | Meaning                                                |
| -------------------------- | -------- | ------------------------------------------------------ |
| `ENCODING_NON_UTF8`        | warning  | File is not UTF-8; decoded with the detected encoding  |
| `ENCODING_UNDETECTED`      | error    | Encoding could not be determined with confidence       |
| `DELIMITER_SNIFFED`        | info     | Delimiter detected from a sample (not the default `,`) |
| `MALFORMED_ROWS`           | warning  | Rows with inconsistent field counts                    |
| `EMPTY_FILE`               | error    | File contains no data                                  |
| `DUPLICATE_COLUMN_NAMES`   | warning  | Two or more columns share a name                       |
| `EMPTY_COLUMN_NAME`        | warning  | A column has a blank/unnamed header                    |
| `MIXED_TYPE_COLUMN`        | warning  | Object column mixes incompatible Python types          |
| `ALL_NULL_COLUMN`          | warning  | Every value in the column is null                      |
| `CONSTANT_COLUMN`          | info     | Column has a single distinct value                     |
| `DUPLICATE_ROWS`           | info     | Fully-duplicated rows present                          |
| `UNSUPPORTED_FILE_SKIPPED` | info     | No registered reader for the file's extension          |
| `INGESTION_FAILED`         | error    | File could not be read or extracted                    |
| `EMPTY_DATASET`            | warning  | The folder contains no ingestible files                |

## Profiles

With `profile=True` (the default), every file gets one `ColumnProfile` per
column: `dtype`, null count and percentage, unique count, cardinality
percentage, and up to 5 stringified sample values — a fast first look at data
quality without opening a notebook.

## Reproducible metadata

All outputs land under `<data_dir>/.smartdataranger/`:

```text
data/
└── .smartdataranger/
    ├── metadata.json    # reproducible import recipes
    └── extracted/       # contents of ingested .zip archives
```

`metadata.json` records, per file, exactly how it was read:

```json
{
  "file_name": "sales_q1.csv",
  "file_type": ".csv",
  "reader": "csv",
  "reader_kwargs": {"encoding": "latin-1", "sep": ";"},
  "columns": ["order_id", "region", "amount"],
  "row_count": 1204,
  "source": "sales_q1.csv"
}
```

`load_dataset` rebuilds the exact same DataFrames from it:

```python
from pathlib import Path

from smartdataranger import load_dataset

frames = load_dataset(Path("data/.smartdataranger/metadata.json"))
```

The `reader` field is a key into a whitelisted reader registry, and
`reader_kwargs` are plain keyword arguments passed to that reader — the file
never contains code and nothing in it is ever executed.

## Known limitations

- Passing a single `.zip` file (rather than a folder containing one) yields
  `({}, report)` with an `EMPTY_DATASET` diagnostic — extracted members can't
  be traced back to the archive path. Put the archive in a folder and scan that.
- Passing a single data file scans its parent folder under the hood, so with
  `write_metadata=True` the written `metadata.json` covers sibling files too;
  the returned frames are filtered to the requested file.
- Encoding detection on short non-UTF-8 samples is heuristic: byte-compatible
  encodings (e.g. `latin-1` vs `cp1250`) may be reported interchangeably.

## Development

```sh
uv sync                     # install with dev dependencies
uv run ruff check .         # lint
uv run ruff format --check .
uv run mypy                 # type-check (strict)
uv run pytest               # full suite, including the e2e pipeline tests
```

## License

[MIT](LICENSE)
