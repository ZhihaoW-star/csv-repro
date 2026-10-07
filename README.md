# csv-repro

**Turn CSV data into a small, pseudonymized bug-report fixture. Locally.**

[中文说明](README.zh-CN.md) · [Examples](examples) · [Contributing](CONTRIBUTING.md) · MIT license

When someone says “please share a reproducible example,” production data is often the thing you cannot share. `csv-repro` replaces values, keeps repeated-value relationships, and writes CSV fixtures plus a Markdown table you can review and paste into an issue.

Python 3.10+ · **zero runtime dependencies** · no account, server, API key, uploads, or telemetry.

> This is **pseudonymization, not anonymization**. Review every artifact before sharing. Repeated values, missing values, order, and relationships can still disclose information. Explicit `--keep` options retain original data. Substitution may stop your bug from reproducing.

## Try the synthetic demo in one minute

```bash
git clone https://github.com/ZhihaoW-star/csv-repro.git
cd csv-repro
python3 csv_repro.py examples/customers.csv examples/orders.csv \
  --link 1:1,2:2 --keep 2:3 -o fixture
python3 fixture/repro.py
```

On Windows, use `py` in place of `python3`. All references are **one-based `TABLE:COLUMN`**: the first input is table 1; the second is table 2. `--link 1:1,2:2` links customer IDs in the first table to customer IDs in the second. `--keep 2:3` intentionally retains the synthetic order amounts.

| Synthetic input | Fixture |
| --- | --- |
| customer-A appears in customers and twice in orders | the same replacement ID appears in all three places |
| repeated 120 in the amount column | stays 120 only because `--keep 2:3` was specified |
| real-looking names and free-text notes | replaced, including in the Markdown output |
| source file names and headers | omitted; files are `table_1.csv`, `table_2.csv`; headers are `col_1`, etc. |

The generated folder contains:

- `table_*.csv` — normalized UTF-8 CSV fixtures.
- `example.md` — a table with escaped HTML, pipes, links and line breaks.
- `repro.py` — a stdlib-only loader to which you can add your failing operation; includes an optional pandas example.
- `report.json` — counts and positional transformation settings; no raw value maps or input paths.
- `README.txt` — review checklist and transformation limits.

The synthetic input files in `examples/` are invented demonstration data. No production data is included.

## Use your own data

```bash
# Replace every nonempty cell and all header names; select first 20 data rows.
python3 csv_repro.py input.csv -o bug-fixture

# Keep exactly two selected logical rows (a quoted multiline cell is one row).
python3 csv_repro.py input.csv --rows 0 --include-row 1:7 \
  --include-row 1:42 -o selected-fixture

# Keep a number column and original headers only after reviewing them.
python3 csv_repro.py input.csv --keep 1:3 --keep-headers -o reviewed-fixture

# Input separators and encoding are explicit; UTF-8 BOM is accepted by default.
python3 csv_repro.py input.tsv --delimiter tab -o tsv-fixture
python3 csv_repro.py input.csv --delimiter ';' --encoding cp1252 -o legacy-fixture

# If kept values will be opened in a spreadsheet, opt into formula escaping.
# This changes values, including formula-like negative numbers.
python3 csv_repro.py input.csv --keep 1:3 --excel-safe -o spreadsheet-fixture
```

All output folders must be **new**. Existing folders and source files are never overwritten. Inputs are read only. By default, empty cells stay empty; all other values are replaced within each column. Link groups are explicit and transitive, including across tables. The tool does not infer relationships or guarantee that selected tables have complete foreign-key coverage.

`--include-row TABLE:ROW` adds that logical data row to the first `--rows` records. It does not count the header and keeps original row order. Repeating the same row does not duplicate it.

## Why this instead of a data generator or database masker?

This tool starts with **the rows involved in a support request**, keeps exact equality relationships, and produces a reviewable issue attachment without a database connection or a configuration file. It is not a replacement for full production-database masking. If you need SQLite subsetting, see [pinkmask](https://github.com/dyne/pinkmask); for configurable CSV data generation/masking, see [anonymization-solution](https://github.com/Irrogant/anonymization-solution). No code from those projects is incorporated.

The workflow was motivated by a [community request to make confidential spreadsheet examples easier to share](https://www.reddit.com/r/excel/comments/1iu0tga/). That establishes a problem to investigate, not proof this implementation is the preferred solution.

## Limits to understand before sharing

- No PII detection, free-text redaction, privacy certification or anonymization guarantee. The default replaces **whole cells** and header names, not selected substrings.
- All values become text tokens unless explicitly kept. Date, numeric, whitespace, ordering and parsing bugs may stop reproducing. Verify the failure against the fixture yourself.
- CSV is normalized: original encoding, BOM, quoting choices and byte layout are not preserved. A byte-parser bug needs a hand-reviewed byte fixture instead.
- Only exact string equality is preserved. There is no automatic trimming, case folding, type conversion or orphan-row repair.
- Inputs require headers and consistent column counts. Blank records and ragged rows are rejected rather than silently repaired. Entire files are validated, including rows outside the selected sample.
- Up to 10 tables, 50 MiB per input; Python's standard CSV field-size limit also applies. Intended for small support fixtures. Selecting many rows consumes more memory; there is no streaming output mode.
- `--excel-safe` uses an apostrophe prefix on formula-like values/headers. Spreadsheet import behavior varies; this is not a universal protection guarantee. Prefer a text editor for reviewing fixtures.
- Deterministic for the same inputs, input order and options. Labels can change when rows or table order change. Mapping dictionaries exist only during the run and are not exported.
- The tool does not submit issues, capture your environment, or automatically prove a bug still exists.

## Install the optional command

The direct script above needs no installation. To get a `csv-repro` command in your own virtual environment:

```bash
python3 -m venv .venv
# macOS / Linux:
. .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
csv-repro --help
```

This project is distributed from GitHub; **no PyPI publication is claimed**.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests exercise linked IDs, deterministic artifacts, BOM/Unicode/multiline inputs, malformed data, error-message disclosure, Markdown escaping, formula handling and existing-output protection. CI runs the suite on Linux, macOS and Windows. Code and documentation were created with Codex assistance and reviewed/tested during development.

If you use it in a real support request, please tell us whether the bug still reproduces and what setup was confusing. Use synthetic examples in issues. A GitHub star helps people find the project when they need it again.
