# Smart Data Ranger

SmartDataRanger is a Python library for **reliable dataset onboarding**.
It focuses on the hardest and most time-consuming part of data work: getting messy files into trustworthy DataFrames and understanding what went wrong when they fail.

The core idea is simple:

* Make data imports deterministic and reproducible
* Detect and explain common data issues early
* Use AI only where human judgment is normally required

AI is an assistant, not the execution engine.

---

## What problem this solves

Most data work still starts with:

* Broken imports
* Wrong encodings
* Silent dtype corruption
* Ambiguous headers
* Inconsistent schemas across files
* Trial and error fixes copied from past projects

SmartDataRanger turns this into a **repeatable onboarding step** with clear artifacts and explanations.

---

## Design principles

* Deterministic by default
* Safe and auditable transformations
* Human approval over automatic fixes
* Works in scripts, notebooks, and CI
* AI explains and suggests, never silently mutates data

---

## Core features

### Dataset discovery and import

* Auto-detect static files in a folder
* Support for CSV, Excel, Parquet, JSON, TXT
* Robust handling of encoding, delimiters, headers, and schemas

### Import contracts

* Generate a versioned import contract (YAML or JSON)
* Reuse the contract to guarantee reproducible reloads
* Fail loudly when incoming data drifts from expectations

### Data diagnostics

* Detect common issues:

  * mixed dtypes
  * broken dates
  * unexpected nulls
  * duplicated rows
  * inconsistent columns across files
* Produce a structured import report

### AI-assisted explanations

* Plain-English explanations of import failures
* Context-aware suggestions grounded in the actual dataset
* Suggested fixes rendered as executable pandas code
* All fixes are opt-in and traceable

---

## Example

```python
from smartdataranger import import_dataset

df, report = import_dataset("./raw_data")
```

Reusing the same contract later:

```python
df = import_dataset("./raw_data", contract="import_contract.yaml")
```

If something breaks, SmartDataRanger explains why and what changed.

---

## Intended users

* Data scientists
* Analytics engineers
* Data analysts
* Anyone tired of rewriting data import logic per project

---

## Status

Work in progress.
The API is evolving and feedback is welcome.