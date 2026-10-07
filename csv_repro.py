#!/usr/bin/env python3
"""Make local, pseudonymized CSV fixtures for reproducible bug reports."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

__version__ = "0.1.0"
MAX_BYTES = 50 * 1024 * 1024


class ReproError(ValueError):
    """An input or policy error whose message does not contain source values."""


def reference(value: str) -> tuple[int, int]:
    """A table:column reference, both one-based."""
    if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", value):
        raise ReproError("Use one-based table:column references, for example 1:2.")
    a, b = value.split(":")
    return int(a) - 1, int(b) - 1


def formula_like(value: str) -> bool:
    return bool(value) and (value[0] in "\t\r\n" or value.lstrip().startswith(("=", "+", "-", "@")))


def excel_text(value: str) -> str:
    return "'" + value if formula_like(value) else value


def markdown_cell(value: str) -> str:
    # Encode markup as visible text. Never turn kept cells into links or HTML.
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("|", "&#124;").replace("`", "&#96;").replace("[", "&#91;")
            .replace("]", "&#93;").replace("\\", "&#92;")
            .replace("*", "&#42;").replace("_", "&#95;").replace("~", "&#126;")
            .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>"))


def read_sample(path: Path, index: int, rows: int, includes: set[int], delimiter: str, encoding: str):
    if path.stat().st_size > MAX_BYTES:
        raise ReproError(f"Table {index + 1} exceeds the 50 MiB input limit.")
    selected = []
    with path.open("r", encoding=encoding, newline="") as stream:
        reader = csv.reader(stream, delimiter=delimiter, strict=True)
        try:
            headers = next(reader)
        except StopIteration:
            raise ReproError(f"Table {index + 1} is empty; a header row is required.") from None
        if not headers:
            raise ReproError(f"Table {index + 1} has no header columns.")
        count = 0
        for count, record in enumerate(reader, 1):
            if len(record) != len(headers):
                raise ReproError(f"Table {index + 1}, data row {count} has a different column count. No output written.")
            if count <= rows or count in includes:
                selected.append(record)
        if any(row > count for row in includes):
            raise ReproError(f"An included row does not exist in table {index + 1}.")
    return headers, selected, count


def make_bundle(inputs: list[Path], output: Path, *, rows=20, includes=(), keeps=(), links=(),
                keep_headers=False, delimiter=",", encoding="utf-8-sig", excel_safe=False):
    """Return an audit report; read sources only and create a NEW output directory.

    Defaults replace all nonempty cells and all header names. Equality is kept
    per column; explicit link groups share a substitution dictionary. This is
    pseudonymization, not anonymization or a guarantee of shareability.
    """
    if not inputs or rows < 0:
        raise ReproError("Provide at least one CSV and a nonnegative row limit.")
    if len(delimiter) != 1 or delimiter in '\r\n"':
        raise ReproError("The delimiter must be one non-newline, non-quote character.")
    if output.exists() or output.is_symlink():
        raise ReproError("The output path already exists. Choose a new directory.")
    if len(inputs) > 10:
        raise ReproError("At most ten input tables are supported in one bundle.")
    if any(not p.is_file() for p in inputs):
        raise ReproError("An input is missing or is not a regular file.")
    requested = [set() for _ in inputs]
    for item in includes:
        table, row = reference(item)  # second component is a data row here
        if table >= len(inputs):
            raise ReproError("An included row references a nonexistent table.")
        requested[table].add(row + 1)
    samples = []
    # Validate whole inputs, not just the selected prefix. Raw cells stay in memory.
    for i, path in enumerate(inputs):
        try:
            samples.append(read_sample(path, i, rows, requested[i], delimiter, encoding))
        except (UnicodeError, csv.Error):
            raise ReproError(f"Table {i + 1} cannot be decoded or parsed. Check --encoding and --delimiter.") from None
    all_refs = {(t, c) for t, (headers, _, _) in enumerate(samples) for c in range(len(headers))}
    kept = {reference(item) for item in keeps}
    if not kept <= all_refs:
        raise ReproError("A kept column references a nonexistent table or column.")
    # Disjoint-set union makes overlapping link groups transitive and order-independent.
    parent = {r: r for r in all_refs}

    def root(r):
        while parent[r] != r:
            parent[r] = parent[parent[r]]
            r = parent[r]
        return r

    for group in links:
        refs = [reference(item) for item in group.split(",")]
        if len(refs) < 2 or not set(refs) <= all_refs:
            raise ReproError("Each link group needs at least two existing table:column references.")
        if set(refs) & kept:
            raise ReproError("A kept column cannot be linked; linking requires substitution.")
        for ref in refs[1:]:
            a, b = root(refs[0]), root(ref)
            parent[max(a, b)] = min(a, b)
    domains = {ref: root(ref) for ref in all_refs}
    domain_ids = {ref: n for n, ref in enumerate(sorted(set(domains.values())), 1)}
    maps = {ref: {} for ref in domain_ids}
    tables = []
    formula_count = 0
    for t, (headers, records, total) in enumerate(samples):
        out_headers = headers[:] if keep_headers else [f"col_{i + 1}" for i in range(len(headers))]
        out_rows = []
        for record in records:
            converted = []
            for c, value in enumerate(record):
                ref = (t, c)
                if ref not in kept and value:
                    domain = domains[ref]
                    mapping = maps[domain]
                    if value not in mapping:
                        mapping[value] = f"value_{domain_ids[domain]}_{len(mapping) + 1}"
                    value = mapping[value]
                formula_count += int(formula_like(value))
                converted.append(excel_text(value) if excel_safe else value)
            out_rows.append(converted)
        formula_count += sum(formula_like(h) for h in out_headers)
        if excel_safe:
            out_headers = [excel_text(h) for h in out_headers]
        tables.append((out_headers, out_rows, total))
    warnings = [
        "Pseudonymized, not anonymized. Repeated values, emptiness, ordering and relationships can identify people or organizations.",
        "Review every generated artifact before sharing. No bug-preservation guarantee: substituted values may change the failing behavior.",
        "UTF-8 comma-separated output is normalized; original byte layout, quoting and encoding are not preserved.",
    ]
    if kept:
        warnings.append("Explicitly kept columns contain original values. Review them before sharing.")
    if keep_headers:
        warnings.append("Original header names are retained by explicit request.")
    if formula_count:
        warnings.append("Formula-like kept values or headers were detected. " + ("An apostrophe prefix was applied by --excel-safe; this changes values and is not a universal spreadsheet security guarantee." if excel_safe else "CSV is a text fixture; use --excel-safe before opening it in a spreadsheet. That option changes values."))
    report = {
        "tool": "csv-repro", "version": __version__, "tables": [
            {"file": f"table_{i + 1}.csv", "input_data_rows": total,
             "selected_data_rows": len(records), "columns": len(headers)}
            for i, (headers, records, total) in enumerate(tables)],
        "kept_columns": [f"{t + 1}:{c + 1}" for t, c in sorted(kept)],
        "kept_headers": keep_headers,
        "linked_columns": [[f"{t + 1}:{c + 1}" for t, c in sorted(all_refs) if domains[t, c] == d]
                           for d in sorted(domain_ids) if sum(domains[r] == d for r in all_refs) > 1],
        "formula_like_cells": formula_count, "excel_safe": excel_safe, "warnings": warnings,
    }
    # Stage everything before creating the destination. Do not overwrite source or existing output.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".csv-repro-", dir=output.parent) as stage_name:
        stage = Path(stage_name)
        markdown = ["# CSV reproduction fixture", "", *[f"> {w}" for w in warnings], ""]
        for i, (headers, records, _) in enumerate(tables, 1):
            with (stage / f"table_{i}.csv").open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(headers)
                writer.writerows(records)
            markdown += [f"## Table {i}", "", "| " + " | ".join(map(markdown_cell, headers)) + " |",
                         "| " + " | ".join("---" for _ in headers) + " |"]
            markdown += ["| " + " | ".join(map(markdown_cell, record)) + " |" for record in records]
            markdown += [""]
        (stage / "example.md").write_text("\n".join(markdown), encoding="utf-8")
        (stage / "report.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        script = '''"""Inspect this local fixture. Replace the print with your failing operation."""
import csv
from pathlib import Path

folder = Path(__file__).resolve().parent
for path in sorted(folder.glob("table_*.csv")):
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    print(path.name, "columns:", rows[0], "data rows:", len(rows) - 1)

# Optional, if pandas is installed:
# import pandas as pd
# df = pd.read_csv(folder / "table_1.csv", dtype=str, keep_default_na=False)
# print(df)
'''
        (stage / "repro.py").write_text(script, encoding="utf-8")
        (stage / "README.txt").write_text(
            "Review every artifact before sharing. No source file names or value maps are included.\n"
            "Run python repro.py to inspect the fixtures. Add a failing operation and your expected result.\n"
            "No source-specific exception, configuration or Python environment is captured.\n\n" + "\n".join(warnings) + "\n", encoding="utf-8")
        # mkdir is exclusive, so even a concurrent writer cannot make us replace an existing directory.
        try:
            output.mkdir(mode=0o700)
        except FileExistsError:
            raise ReproError("The output path already exists. Choose a new directory.") from None
        written = []
        try:
            for artifact in stage.iterdir():
                target = output / artifact.name
                with target.open("xb") as dest, artifact.open("rb") as src:
                    written.append(target)
                    shutil.copyfileobj(src, dest)
        except BaseException:
            for path in written:
                path.unlink(missing_ok=True)
            try:
                output.rmdir()
            except OSError:
                pass
            raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="All values and headers are substituted by default. Pseudonymization is not anonymization; review the output before sharing.")
    parser.add_argument("inputs", nargs="+", type=Path, help="header-bearing CSV files, ordered as tables 1, 2, ...")
    parser.add_argument("-o", "--output", required=True, type=Path, help="NEW output directory (never overwritten)")
    parser.add_argument("--rows", type=int, default=20, help="first N data rows per table (default 20; 0 selects only included rows)")
    parser.add_argument("--include-row", action="append", default=[], help="also include data row TABLE:ROW (repeatable, one-based)")
    parser.add_argument("--keep", action="append", default=[], help="keep original values in TABLE:COLUMN (repeatable, one-based)")
    parser.add_argument("--link", action="append", default=[], help="share substitutions across TABLE:COLUMN,... (repeatable)")
    parser.add_argument("--keep-headers", action="store_true", help="retain original header names explicitly")
    parser.add_argument("--delimiter", default=",", help="input separator, default comma; use 'tab' for TSV")
    parser.add_argument("--encoding", default="utf-8-sig", help="input encoding (default utf-8-sig accepts UTF-8 with/without BOM)")
    parser.add_argument("--excel-safe", action="store_true", help="prefix formula-like output cells with an apostrophe; changes values")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        report = make_bundle(args.inputs, args.output, rows=args.rows, includes=args.include_row,
                             keeps=args.keep, links=args.link, keep_headers=args.keep_headers,
                             delimiter="\t" if args.delimiter == "tab" else args.delimiter,
                             encoding=args.encoding, excel_safe=args.excel_safe)
    except (ReproError, OSError, LookupError) as error:
        # OSError filenames may contain personal details; do not print their raw message.
        message = str(error) if isinstance(error, ReproError) else "Cannot read/write files or use the requested encoding. No source content is printed."
        parser.exit(2, f"csv-repro: {message}\n")
    print(f"Created {len(report['tables'])} fixture table(s). Review every artifact before sharing.")
    for warning in report["warnings"]:
        print(f"Note: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
